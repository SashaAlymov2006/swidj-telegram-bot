import os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
from state_store import StateStore
from studio_presets import change,load,settings
from studio_presets_bot import handle,show
from media_store import MediaStore

class PresetTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=StateStore(Path(self.tmp.name)/'state.db')
        self.item=(await change(self.store,77,{'action':'save','name':'My sound','settings':{'pitch':-2,'speed':1.25,'effects':['reverb'],'params':{'room_s':2.2}}}))[0]
        self.update=NS(effective_user=NS(id=77),effective_chat=NS(id=77,type='private'),effective_message=NS(reply_text=AsyncMock()),callback_query=NS(data='preset:apply:'+self.item['id'],answer=AsyncMock()))
        self.context=NS(user_data={'language':'en'},bot=NS())

    async def test_chat_lists_the_same_saved_app_presets(self):
        with patch('studio_presets_bot.screen',new=AsyncMock()) as screen:
            await show(self.update,self.context,self.store)
        buttons=[button for row in screen.await_args.args[2] for button in row]
        self.assertTrue(any(button.text=='My sound' and button.callback_data.endswith(self.item['id']) for button in buttons))
        self.assertIn('My sound presets',screen.await_args.args[1])

    async def test_chat_applies_full_validated_sound_to_owned_source(self):
        root=Path(self.tmp.name)/'audio';source=Path(self.tmp.name)/'input.mp3';source.write_bytes(b'original');target=Path(self.tmp.name)/'mix.mp3';target.write_bytes(b'mixed')
        self.context.user_data.update(last_audio_path=MediaStore(root).retain(77,source),downloaded_song={'id':1,'title':'Track'})
        async def retain(context,uid,path):context.user_data['last_audio_path']=MediaStore(root).retain(uid,path)
        with patch.dict(os.environ,{'AUDIO_CACHE_DIR':str(root)}),patch('miniapp_studio.render',new=AsyncMock(return_value=target)) as render,patch('miniapp_studio.probe',new=AsyncMock(return_value=120)),patch('audio_presentation.send_music',new=AsyncMock(return_value=NS(audio=NS(file_id='fixture-file')))) as send:
            await handle(self.update,self.context,self.store,retain)
        config=render.await_args.args[2]
        self.assertEqual(config['pitch'],-2);self.assertEqual(config['speed'],1.25);self.assertEqual(config['format'],'mp3')
        self.assertNotIn('preview',config)
        send.assert_awaited_once();self.assertEqual(self.context.user_data['downloaded_song']['file_id'],'fixture-file')
        self.assertEqual(Path(self.context.user_data['last_audio_path']).read_bytes(),b'mixed')

    async def test_preset_limit_and_hostile_values_do_not_replace_saved_sound(self):
        for index in range(19):await change(self.store,77,{'action':'save','name':str(index),'settings':{}})
        with self.assertRaises(OverflowError):await change(self.store,77,{'action':'save','name':'Overflow','settings':{}})
        for value in ({'speed':float('nan')},{'pitch':True},{'effects':[{}]},{'params':{'unknown':1}}):
            with self.assertRaises(ValueError):settings(value)
        self.assertEqual(len(await load(self.store,77)),20)

    async def test_another_users_active_file_cannot_be_processed(self):
        root=Path(self.tmp.name)/'audio';source=Path(self.tmp.name)/'input.mp3';source.write_bytes(b'private')
        self.context.user_data['last_audio_path']=MediaStore(root).retain(78,source)
        with patch.dict(os.environ,{'AUDIO_CACHE_DIR':str(root)}),patch('miniapp_studio.render',new=AsyncMock()) as render:
            await handle(self.update,self.context,self.store,AsyncMock())
        render.assert_not_awaited();self.update.effective_message.reply_text.assert_awaited_once()
