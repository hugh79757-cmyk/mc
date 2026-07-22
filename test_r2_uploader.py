"""Tests for image/r2_uploader.py — R2 버킷 분기 로직."""


class TestResolveBucket:
    """_resolve_bucket() 사이트별 버킷 분기 테스트."""

    def test_techpawz_uses_techpawz_images(self):
        """techpawz-images 버킷 분기 확인."""
        from image.r2_uploader import _resolve_bucket
        assert _resolve_bucket("images/techpawz") == "techpawz-images"

    def test_rotcha_uses_hotissue_images(self):
        """rotcha는 기본 hotissue-images 버킷 사용 (비회귀)."""
        from image.r2_uploader import _resolve_bucket
        assert _resolve_bucket("images/rotcha") == "hotissue-images"

    def test_informationhot_uses_hotissue_images(self):
        """informationhot은 기본 hotissue-images 버킷 사용 (비회귀)."""
        from image.r2_uploader import _resolve_bucket
        assert _resolve_bucket("images/informationhot") == "hotissue-images"

    def test_unknown_prefix_uses_default(self):
        """미등록 prefix는 기본 버킷 반환."""
        from image.r2_uploader import _resolve_bucket, R2_BUCKET_NAME
        assert _resolve_bucket("images/unknown") == R2_BUCKET_NAME

    def test_r2_site_buckets_dict_exists(self):
        """R2_SITE_BUCKETS 딕셔너리 존재 확인."""
        from image.r2_uploader import R2_SITE_BUCKETS
        assert "images/techpawz" in R2_SITE_BUCKETS
        assert R2_SITE_BUCKETS["images/techpawz"] == "techpawz-images"
