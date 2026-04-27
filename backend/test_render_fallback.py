import os
import unittest
from unittest.mock import patch

os.environ["TRUESIGHT_EMBEDDING_BACKEND"] = "fallback"

import app


class RenderFallbackStartupTest(unittest.TestCase):
    def fail_if_clip_loads(self):
        raise AssertionError("CLIP should not load when fallback embeddings are configured")

    def test_startup_does_not_load_clip_when_fallback_is_configured(self):
        with patch.object(app, "load_clip_backend", side_effect=self.fail_if_clip_loads):
            app.on_startup()

    def test_health_and_root_do_not_load_clip_when_fallback_is_configured(self):
        with patch.object(app, "load_clip_backend", side_effect=self.fail_if_clip_loads):
            self.assertEqual(app.health()["embedding_backend"], "fallback_rgb_embedding")
            self.assertEqual(app.root()["embedding_backend"], "fallback_rgb_embedding")


if __name__ == "__main__":
    unittest.main()
