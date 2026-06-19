"""
Deduplication Engine — Configurable record deduplication.

Supports multiple deduplication strategies:
- Exact match: Hash-based deduplication on key columns
- Fuzzy match: Similarity-based deduplication for messy data
- Window-based: Time-windowed deduplication for streaming data
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class DeduplicationStrategy(Enum):
    """Deduplication strategy type."""
    EXACT = "exact"      # Hash-based exact match
    FUZZY = "fuzzy"      # Similarity-based fuzzy match
    WINDOW = "window"    # Time-window based


class KeepStrategy(Enum):
    """Which duplicate to keep."""
    FIRST = "first"
    LAST = "last"
    MOST_COMPLETE = "most_complete"  # Keep the record with fewest nulls


@dataclass
class DeduplicationResult:
    """Result of a deduplication operation."""
    total_input: int = 0
    total_output: int = 0
    duplicates_found: int = 0
    duplicates_removed: int = 0
    strategy_used: str = ""
    key_columns: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    sample_duplicates: list[dict[str, Any]] = field(default_factory=list)

    @property
    def dedup_rate(self) -> float:
        if self.total_input == 0:
            return 0.0
        return (self.duplicates_removed / self.total_input) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_input": self.total_input,
            "total_output": self.total_output,
            "duplicates_found": self.duplicates_found,
            "duplicates_removed": self.duplicates_removed,
            "dedup_rate_pct": round(self.dedup_rate, 2),
            "strategy": self.strategy_used,
            "key_columns": self.key_columns,
            "duration_seconds": round(self.duration_seconds, 2),
            "sample_duplicates": self.sample_duplicates[:5],
        }


class DeduplicationEngine:
    """
    Configurable record deduplication engine.

    Supports multiple strategies for different use cases:
    - Exact match: For structured data with reliable keys
    - Fuzzy match: For messy data where keys may have typos
    - Window-based: For streaming data with time-based dedup

    Usage:
        engine = DeduplicationEngine(
            strategy=DeduplicationStrategy.EXACT,
            key_columns=["transaction_id", "source_system"],
            keep=KeepStrategy.LAST,
        )
        df_deduped, result = engine.deduplicate(df)
        print(f"Removed {result.duplicates_removed} duplicates")
    """

    def __init__(
        self,
        strategy: DeduplicationStrategy = DeduplicationStrategy.EXACT,
        key_columns: list[str] | None = None,
        keep: KeepStrategy = KeepStrategy.FIRST,
        window_hours: int = 24,
        similarity_threshold: float = 0.85,
    ):
        self.strategy = strategy
        self.key_columns = key_columns or []
        self.keep = keep
        self.window_hours = window_hours
        self.similarity_threshold = similarity_threshold

    def deduplicate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, DeduplicationResult]:
        """
        Remove duplicate records from a DataFrame.

        Args:
            df: Input DataFrame with potential duplicates.

        Returns:
            Tuple of (deduplicated DataFrame, DeduplicationResult).
        """
        start = datetime.now(timezone.utc)
        result = DeduplicationResult(
            total_input=len(df),
            strategy_used=self.strategy.value,
            key_columns=self.key_columns,
        )

        if df.empty:
            result.total_output = 0
            return df, result

        if self.strategy == DeduplicationStrategy.EXACT:
            df_out = self._exact_dedup(df, result)
        elif self.strategy == DeduplicationStrategy.FUZZY:
            df_out = self._fuzzy_dedup(df, result)
        elif self.strategy == DeduplicationStrategy.WINDOW:
            df_out = self._window_dedup(df, result)
        else:
            df_out = df

        result.total_output = len(df_out)
        result.duplicates_removed = result.total_input - result.total_output
        result.duration_seconds = (
            datetime.now(timezone.utc) - start
        ).total_seconds()

        logger.info(
            f"Deduplication complete: {result.duplicates_removed} duplicates removed "
            f"({result.dedup_rate:.1f}%), strategy={self.strategy.value}"
        )

        return df_out, result

    def _exact_dedup(
        self, df: pd.DataFrame, result: DeduplicationResult
    ) -> pd.DataFrame:
        """
        Hash-based exact deduplication.

        Creates a hash of key columns and removes rows with matching hashes.
        """
        # Determine key columns
        cols = [c for c in self.key_columns if c in df.columns]
        if not cols:
            # Use all columns if no key columns specified
            cols = [c for c in df.columns if not c.startswith("_")]

        # Add hash column for tracking
        df = df.copy()
        df["_dedup_hash"] = df[cols].apply(
            lambda row: hashlib.md5(
                "|".join(str(v) for v in row.values).encode()
            ).hexdigest(),
            axis=1,
        )

        # Find duplicates
        dup_mask = df.duplicated(subset=["_dedup_hash"], keep=False)
        result.duplicates_found = dup_mask.sum()

        # Collect samples of duplicates
        if result.duplicates_found > 0:
            dup_groups = df[dup_mask].groupby("_dedup_hash")
            for hash_val, group in list(dup_groups)[:3]:
                result.sample_duplicates.append({
                    "hash": hash_val,
                    "count": len(group),
                    "key_values": group[cols].head(2).to_dict("records"),
                })

        # Remove duplicates
        if self.keep == KeepStrategy.MOST_COMPLETE:
            # Keep the row with the fewest nulls
            df["_null_count"] = df.isna().sum(axis=1)
            df = df.sort_values("_null_count", ascending=True)
            df = df.drop_duplicates(subset=["_dedup_hash"], keep="first")
            df = df.drop(columns=["_null_count"])
        else:
            keep_param = self.keep.value if self.keep != KeepStrategy.MOST_COMPLETE else "first"
            df = df.drop_duplicates(subset=["_dedup_hash"], keep=keep_param)

        # Remove hash column
        df = df.drop(columns=["_dedup_hash"])
        return df.reset_index(drop=True)

    def _fuzzy_dedup(
        self, df: pd.DataFrame, result: DeduplicationResult
    ) -> pd.DataFrame:
        """
        Similarity-based fuzzy deduplication.

        Uses string similarity metrics to find near-duplicates.
        Useful for data from sources with inconsistent formatting.
        """
        cols = [c for c in self.key_columns if c in df.columns]
        if not cols:
            logger.warning("No key columns for fuzzy dedup, falling back to exact")
            return self._exact_dedup(df, result)

        # For large datasets, use blocking to reduce comparisons
        # Simple implementation: group by first few chars of key columns
        df = df.copy()

        # Create a normalized key for blocking
        def normalize_key(row: pd.Series) -> str:
            parts = []
            for col in cols:
                val = str(row.get(col, "")).lower().strip()
                parts.append(val[:5])  # First 5 chars for blocking
            return "|".join(parts)

        df["_block_key"] = df.apply(normalize_key, axis=1)

        # Within each block, find similar records
        indices_to_remove: set[int] = set()
        blocks = df.groupby("_block_key")

        for _, block in blocks:
            if len(block) < 2:
                continue

            for i, (idx_a, row_a) in enumerate(block.iterrows()):
                if idx_a in indices_to_remove:
                    continue
                for idx_b, row_b in list(block.iterrows())[i + 1:]:
                    if idx_b in indices_to_remove:
                        continue

                    similarity = self._calculate_similarity(row_a, row_b, cols)
                    if similarity >= self.similarity_threshold:
                        result.duplicates_found += 1
                        indices_to_remove.add(idx_b)

        df = df.drop(index=list(indices_to_remove))
        df = df.drop(columns=["_block_key"])
        return df.reset_index(drop=True)

    def _window_dedup(
        self, df: pd.DataFrame, result: DeduplicationResult
    ) -> pd.DataFrame:
        """
        Time-windowed deduplication.

        Removes duplicates that appear within a specified time window.
        Designed for streaming data where the same event might be
        delivered multiple times.
        """
        # Find timestamp column
        time_col = None
        for col in ["timestamp", "_ingested_at", "created_at", "event_time"]:
            if col in df.columns:
                time_col = col
                break

        if time_col is None:
            logger.warning("No timestamp column found, falling back to exact dedup")
            return self._exact_dedup(df, result)

        cols = [c for c in self.key_columns if c in df.columns]
        if not cols:
            cols = [c for c in df.columns if not c.startswith("_")]

        df = df.copy()
        df["_ts"] = pd.to_datetime(df[time_col], errors="coerce", utc=True)
        df = df.sort_values("_ts")

        indices_to_remove: set[int] = set()

        for i in range(len(df)):
            if df.index[i] in indices_to_remove:
                continue

            row = df.iloc[i]
            window_end = row["_ts"] + pd.Timedelta(hours=self.window_hours)

            # Look ahead within window
            for j in range(i + 1, len(df)):
                if df.index[j] in indices_to_remove:
                    continue
                other = df.iloc[j]

                if other["_ts"] > window_end:
                    break

                # Check if key columns match
                is_dup = all(
                    str(row.get(c, "")) == str(other.get(c, ""))
                    for c in cols
                )
                if is_dup:
                    result.duplicates_found += 1
                    indices_to_remove.add(df.index[j])

        df = df.drop(index=list(indices_to_remove))
        df = df.drop(columns=["_ts"], errors="ignore")
        return df.reset_index(drop=True)

    @staticmethod
    def _calculate_similarity(
        row_a: pd.Series, row_b: pd.Series, columns: list[str]
    ) -> float:
        """Calculate string similarity between two rows."""
        similarities: list[float] = []

        for col in columns:
            val_a = str(row_a.get(col, "")).lower().strip()
            val_b = str(row_b.get(col, "")).lower().strip()

            if not val_a and not val_b:
                similarities.append(1.0)
                continue
            if not val_a or not val_b:
                similarities.append(0.0)
                continue

            # Simple character-level similarity (Jaccard on character bigrams)
            bigrams_a = set(val_a[i:i+2] for i in range(len(val_a) - 1))
            bigrams_b = set(val_b[i:i+2] for i in range(len(val_b) - 1))

            if not bigrams_a and not bigrams_b:
                similarities.append(1.0 if val_a == val_b else 0.0)
            else:
                intersection = len(bigrams_a & bigrams_b)
                union = len(bigrams_a | bigrams_b)
                similarities.append(intersection / max(union, 1))

        return sum(similarities) / max(len(similarities), 1)
