import sys
from pathlib import Path

# Put backend/ on sys.path so tests can `import app.*` regardless of the
# directory pytest is invoked from (repo root or backend/).
sys.path.insert(0, str(Path(__file__).parent))
