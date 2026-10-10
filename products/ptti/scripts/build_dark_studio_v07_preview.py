"""Build Dark Studio with the existing guarded Windows Preview toolchain."""
import build_dual_source_v061_preview as preview

preview.NAME = "PTTI-Dark-Studio-v0.7-Preview"
preview.PRODUCT_NAME = "PTTI Dark Studio"
preview.VERSION = "0.7"
preview.BUILD_PREFIX = "dark-studio-v07"
preview.DATABASE_SUBDIR = "DarkStudio-v07-Preview"

if __name__ == "__main__":
    preview.main()
