from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ht_l1_core.schema.provenance import BronzeProvenanceSchema


def test_bronze_provenance_schema_validates_non_null_columns():
    row = {
        "source": "unit-test",
        "source_fetched_at": datetime(2026, 5, 5),
        "ingested_at": datetime(2026, 5, 5),
        "content_hash": "abc123",
    }

    validated = BronzeProvenanceSchema.validate(pd.DataFrame([row]))

    assert validated[list(row)].notna().all().all()
    assert all(not BronzeProvenanceSchema.columns[column].nullable for column in row)
