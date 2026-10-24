import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from owner_panel import Controls
from state_store import StateStore


class OwnerControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_settings_persist_and_owner_cannot_be_locked_out(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.sqlite")
            controls = Controls(store)
            await controls.load()
            await controls.change("maintenance")
            await controls.change("downloads")
            await controls.change("block", 78)
            restored = Controls(store)
            await restored.load()
            self.assertTrue(restored.settings["maintenance"])
            self.assertFalse(restored.enabled("downloads"))
            self.assertIn(78, restored.settings["blocked"])
            context = SimpleNamespace(application=SimpleNamespace(bot_data={"is_owner": lambda _: True}))
            update = SimpleNamespace(effective_user=SimpleNamespace(id=77))
            async def handler(update, context): pass
            self.assertTrue(await restored.admit(handler, update, context))

    async def test_legacy_routes_and_pending_inputs_respect_feature_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            controls = Controls(StateStore(Path(directory) / "state.sqlite"))
            await controls.change("downloads")
            await controls.change("studio")
            context = SimpleNamespace(user_data={}, application=SimpleNamespace(bot_data={"is_owner": lambda _: False}))
            for name, data, pending in [
                ("handle_callback", "download_1", {}),
                ("handle_callback", "recognized_download", {}),
                ("library_callback", "lib:download:1", {}),
                ("voice_callback", "voice_effects", {}),
                ("handle_message", "", {"awaiting_pitch": True}),
                ("handle_message", "", {"awaiting_trim": True}),
                ("handle_callback", "fx:apply:token", {}),
            ]:
                async def handler(update, context): pass
                handler.__name__ = name
                context.user_data = pending
                update = SimpleNamespace(effective_user=SimpleNamespace(id=78),
                    callback_query=SimpleNamespace(data=data), effective_message=SimpleNamespace(reply_text=AsyncMock()))
                self.assertFalse(await controls.admit(handler, update, context), (name, data))
