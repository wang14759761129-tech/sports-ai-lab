"""Cinema Preview using the established resource-guarded build chain."""
import build_dual_source_v061_preview as preview
preview.NAME = "PTTI-Cinema-v0.7.1-Preview"
preview.PRODUCT_NAME = "PTTI Cinema"
preview.VERSION = "0.7.1"
preview.BUILD_PREFIX = "cinema-v071"
preview.DATABASE_SUBDIR = "Cinema-v071-Preview"
if __name__ == "__main__":
    preview.main()
