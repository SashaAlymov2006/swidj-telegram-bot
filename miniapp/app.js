import {AudioEngine, stamp} from './audio.js';
import {liveEffects,dspDefaults} from './live.js';

const paths = {
  charts:'M4 20v-8M10 20V4M16 20V8M2 20h20',
  home:'M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
  search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  library:'M4 4v16M9 4v16M14 4v16M18 4l3 16',
  studio:'M5 3v5m0 4v9M12 3v10m0 4v4M19 3v3m0 4v11M2 8h6m1 9h6m1-11h6',
  play:'m9 5 11 7-11 7Z', pause:'M8 5v14M16 5v14', next:'m5 5 10 7-10 7ZM19 5v14',
  previous:'m19 5-10 7 10 7ZM5 5v14', heart:'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z',
  arrow:'M4 12h16m-6-6 6 6-6 6', plus:'M12 5v14M5 12h14', more:'M5 12h.01M12 12h.01M19 12h.01',
  download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5', upload:'M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5',
  volume:'m11 5-6 4H2v6h3l6 4ZM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14',
  repeat:'m17 2 4 4-4 4M3 11V8a2 2 0 0 1 2-2h16M7 22l-4-4 4-4m14-1v3a2 2 0 0 1-2 2H3',
  info:'M12 11v6m0-10v.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  trash:'M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7',
  folder:'M3 7V4h6l3 3h9v13H3Z', send:'m3 3 19 9-19 9 4-9Zm4 9h15', music:'M9 18V5l12-3v13M9 8l12-3M9 18a3 3 0 1 1-6-1 3 3 0 0 1 6 1M21 15a3 3 0 1 1-6-1 3 3 0 0 1 6 1'
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true" class="${name}"><path d="${paths[name] || paths.music}"/></svg>`;
const e = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $ = id => document.getElementById(id);
const copy = {
  ru:{home:'Главная',search:'Поиск',library:'Моя музыка',studio:'Студия',yourSpace:'ТВОЁ ПРОСТРАНСТВО',makeItYours:'Звучит по-твоему.',railNote:'Чуть больше баса. Совсем другое настроение.',openStudio:'Открыть студию →',musicSpace:'Твоё музыкальное пространство',footer:'Слушай. Создавай. Сохраняй.',demo:'Демо',connected:'В Telegram',heroLabel:'МУЗЫКА БЕЗ ЛИШНИХ ДВИЖЕНИЙ',hero1:'Твоя музыка.',hero2:'Твои правила.',heroNote:'Любимые треки, личные плейлисты и свой звук — в одном месте.',findMusic:'Найти музыку',yourSound:'ТВОЙ ЗВУК — ТВОЙ ВЫБОР',continue:'Включи настроение',continueNote:'Нажми на обложку — и слушай',allMusic:'Вся музыка →',fresh:'Твоя библиотека',freshNote:'Продолжи с того, что сохранил',quickStudio:'Сделай свой микс',quickStudioNote:'Скорость, бас и короткий пример',quickLibrary:'Всё любимое рядом',quickLibraryNote:'Собери плейлист под своё настроение',searchTitle:'Найди свой следующий трек.',searchNote:'Введи название или исполнителя.',searchPlaceholder:'Название песни или исполнитель',searchButton:'Найти',searchEmpty:'Что включим?',searchHint:'Ищи музыку по названию или открой сохранённые треки.',results:'Результаты',searching:'Ищу записи…',noResults:'Ничего не найдено',retrySearch:'Попробуй другое название или добавь исполнителя.',demoSearch:'В деморежиме поиск работает по шести оригинальным инструментальным примерам.',libraryTitle:'Всё твоё. В одном месте.',libraryNote:'Треки, которые хочется оставить.',all:'Все треки',favorites:'Избранное',uploads:'Мои файлы',playlists:'Плейлисты',newPlaylist:'Новый плейлист',playlistName:'Название плейлиста',create:'Создать',cancel:'Отмена',tracks:'треков',emptyLibrary:'Здесь будет твоя музыка',emptyLibraryNote:'Сохрани трек из поиска или добавь свой файл через бота.',emptyPlaylist:'Добавь музыку в плейлист',emptyPlaylistNote:'Открой меню трека и выбери «В плейлист».',addPlaylist:'В плейлист',save:'В избранное',unsave:'Убрать из избранного',remove:'Убрать из библиотеки',removeQuestion:'Убрать трек из избранного и всех плейлистов?',removed:'Трек убран из библиотеки',saved:'Сохранено',created:'Плейлист создан',studioTitle:'Твой трек. Новый характер.',studioNote:'Выбери аудио, настрой звук и послушай результат.',localProcessing:'Обработка на твоём устройстве',chooseFile:'Открыть свой файл',chooseFirst:'Выбери трек или свой аудиофайл',chooseFirstNote:'Аудио остаётся на твоём устройстве.',soundSettings:'Настрой свой звук',soundNote:'Изменения слышны во время воспроизведения.',bass:'Бас',bassLess:'Меньше',bassOff:'Оригинал',bassGentle:'Мягкий',bassMedium:'Средний',bassStrong:'Сильный',speed:'Скорость и тон',slower:'Медленнее',original:'Оригинал',faster:'Быстрее',preview:'Пример · 15 сек',export:'Сохранить микс · WAV',reset:'Сбросить настройки',rendering:'Готовлю аудио…',studioFine:'Скорость меняется вместе с тоном. Экспорт в браузере — до 3 минут. Для длинного трека и MP3 используй студию в боте.',demoNote:'Демо: оригинальные инструментальные примеры. Изменения библиотеки сохраняются только в этом браузере.',demoStudio:'Файл обрабатывается локально, без загрузки на сервер.',selectTrack:'Выбери трек',ready:'Твой следующий любимый звук',play:'Слушать',pause:'Пауза',previous:'Предыдущий трек',next:'Следующий трек',favorite:'В избранное',more:'Действия с треком',sent:'Варианты отправлены в чат бота',send:'Получить в боте',sendNote:'Эта запись пока не загружена. Открой чат бота, чтобы выбрать и скачать полную версию.',openChat:'Открыть чат бота',demoSend:'В деморежиме отправка в Telegram недоступна.',fileTooLarge:'Выбери аудиофайл до 20 МБ.',invalidAudio:'Не удалось открыть аудио. Попробуй MP3, WAV или OGG.',long:'Экспорт в браузере — до 3 минут. Для полного длинного трека используй бота.',error:'Не получилось. Попробуй ещё раз.',expired:'Открой приложение заново из Telegram — вход устарел.',unavailable:'Раздел временно недоступен.',rateLimit:'Подожди несколько секунд и попробуй снова.',previewReady:'Пример готов',exportReady:'Микс сохранён',localSave:'Для постоянного сохранения отправь этот файл боту.',back:'Назад',loading:'Загружаю твою музыку…',authError:'Не удалось подтвердить вход',authHint:'Открой приложение из личного чата с ботом.',repeat:'Повтор трека',seek:'Позиция в треке',volume:'Громкость',language:'Сменить язык',capacity:'Достигнут лимит библиотеки или плейлиста.'},
  en:{home:'Home',search:'Search',library:'Your music',studio:'Studio',yourSpace:'YOUR SPACE',makeItYours:'Make it sound like you.',railNote:'A little more bass. A whole new mood.',openStudio:'Open studio →',musicSpace:'Your personal music space',footer:'Listen. Create. Keep.',demo:'Demo',connected:'In Telegram',heroLabel:'LESS TAPPING. MORE MUSIC.',hero1:'Your music.',hero2:'Your rules.',heroNote:'Favorite tracks, personal playlists and your own sound. All in one place.',findMusic:'Find your music',yourSound:'YOUR SOUND. YOUR CHOICE.',continue:'Find your frequency',continueNote:'Pick a cover. Press play.',allMusic:'All your music →',fresh:'From your collection',freshNote:'Pick up where you left off',quickStudio:'Make it your mix',quickStudioNote:'Speed, bass and a quick preview',quickLibrary:'Keep the good stuff',quickLibraryNote:'Build a playlist for your mood',searchTitle:'Find your next favorite.',searchNote:'Search by song or artist.',searchPlaceholder:'Song title or artist',searchButton:'Search',searchEmpty:'What are we playing?',searchHint:'Find a song or explore your saved music.',results:'Results',searching:'Finding recordings…',noResults:'No tracks found',retrySearch:'Try another title or add the artist.',demoSearch:'Demo search covers six original instrumental samples.',libraryTitle:'All yours. All here.',libraryNote:'For the tracks worth keeping.',all:'All tracks',favorites:'Favorites',uploads:'Your files',playlists:'Playlists',newPlaylist:'New playlist',playlistName:'Playlist name',create:'Create',cancel:'Cancel',tracks:'tracks',emptyLibrary:'Your music starts here',emptyLibraryNote:'Save a search result or send your own file to the bot.',emptyPlaylist:'Make this playlist yours',emptyPlaylistNote:'Open a track menu and choose “Add to playlist”.',addPlaylist:'Add to playlist',save:'Add to favorites',unsave:'Remove from favorites',remove:'Remove from library',removeQuestion:'Remove this track from favorites and all playlists?',removed:'Removed from library',saved:'Saved',created:'Playlist created',studioTitle:'Same track. New energy.',studioNote:'Choose audio, shape the sound and hear the difference.',localProcessing:'Processed on your device',chooseFile:'Open your audio',chooseFirst:'Choose a track or your audio file',chooseFirstNote:'Your file stays on your device.',soundSettings:'Find your sound',soundNote:'Hear your changes while the track plays.',bass:'Bass',bassLess:'Less',bassOff:'Original',bassGentle:'Gentle',bassMedium:'Medium',bassStrong:'Strong',speed:'Speed & pitch',slower:'Slower',original:'Original',faster:'Faster',preview:'Preview · 15 sec',export:'Save mix · WAV',reset:'Reset settings',rendering:'Preparing audio…',studioFine:'Speed changes pitch too. Browser export supports up to 3 minutes. Use the bot studio for longer tracks and MP3.',demoNote:'Demo: original instrumental samples. Library changes stay in this browser.',demoStudio:'Your file is processed locally without a server upload.',selectTrack:'Choose a track',ready:'Your next favorite sound',play:'Play',pause:'Pause',previous:'Previous track',next:'Next track',favorite:'Favorite',more:'Track actions',sent:'Recording choices sent to the bot',send:'Get it in the bot',sendNote:'This recording is not downloaded yet. Open the bot chat to choose and download the full version.',openChat:'Open bot chat',demoSend:'Sending to Telegram is unavailable in demo mode.',fileTooLarge:'Choose an audio file up to 20 MB.',invalidAudio:'Could not open the audio. Try MP3, WAV or OGG.',long:'Browser export supports up to 3 minutes. Use the bot for longer full tracks.',error:'Something went wrong. Please try again.',expired:'Reopen the app from Telegram — your login has expired.',unavailable:'Temporarily unavailable.',rateLimit:'Wait a few seconds and try again.',previewReady:'Preview ready',exportReady:'Mix saved',localSave:'Send this file to the bot to save it permanently.',back:'Back',loading:'Loading your music…',authError:'Could not verify your login',authHint:'Open the app from your private chat with the bot.',repeat:'Repeat track',seek:'Track position',volume:'Volume',language:'Change language',capacity:'Library or playlist limit reached.'}
};
const tg = window.Telegram?.WebApp;
Object.assign(copy.ru,{preparing:'Готовлю полную запись…',queued:'Ожидание свободного места…',cancelling:'Отменяю загрузку…',cancelled:'Загрузка отменена',prepareFailed:'Не удалось подготовить запись. Нажми на трек для повтора или выбери другую версию.',chooseVersion:'Выбери запись',preparingOther:'Дождись загрузки или нажми «Отмена».',readyToPlay:'Трек готов — нажми ▶',downloadTrack:'Скачать аудио',send:'Отправить в чат',sent:'Отправлено в чат. Можно продолжать слушать здесь.',sendNote:'Музыка открывается прямо в приложении.',noResults:'Записи не найдены'});
Object.assign(copy.en,{preparing:'Preparing the full recording…',queued:'Waiting for a free slot…',cancelling:'Cancelling download…',cancelled:'Download cancelled',prepareFailed:'Could not prepare this recording. Tap to retry or choose another version.',chooseVersion:'Choose a recording',preparingOther:'Wait for the download or press Cancel.',readyToPlay:'Track ready — press ▶',downloadTrack:'Download audio',send:'Send to chat',sent:'Sent to chat. You can keep listening here.',sendNote:'Music opens right inside the app.',noResults:'No recordings found'});
Object.assign(copy.ru,{nowPlaying:'Сейчас играет',rename:'Переименовать',deletePlaylist:'Удалить плейлист',playlistDeleteNote:'Плейлист исчезнет. Треки останутся в твоей библиотеке.',playlistDeleted:'Плейлист удалён',saveName:'Сохранить изменения',renamed:'Название изменено',removeFromPlaylist:'Убрать из этого плейлиста',refresh:'Обновить',refreshed:'Библиотека обновлена',long:'Для обработки в браузере выбери трек до 3 минут. Длинные треки обрабатывай в боте.',studioFine:'Скорость меняется вместе с тоном. В браузере исходный трек и готовый WAV — до 3 минут. Для длинного трека и MP3 используй студию бота.'});
Object.assign(copy.en,{nowPlaying:'Now playing',rename:'Rename',deletePlaylist:'Delete playlist',playlistDeleteNote:'The playlist will be removed. Its tracks stay in your library.',playlistDeleted:'Playlist deleted',saveName:'Save changes',renamed:'Name updated',removeFromPlaylist:'Remove from this playlist',refresh:'Refresh',refreshed:'Library refreshed',long:'Browser processing supports tracks up to 3 minutes. Use the bot for longer tracks.',studioFine:'Speed changes pitch too. Browser source audio and exported WAV support up to 3 minutes. Use the bot studio for longer tracks and MP3.'});
Object.assign(copy.ru,{removeUploadQuestion:'??????? ???? ???? ?? ?????????? ? ???? ??????????? ??????????? ?? ??????? ????? ????? ??????? ??? ??????????? ??????????????.'});
Object.assign(copy.en,{removeUploadQuestion:'Delete this file from the library and all playlists? The stored server copy will be permanently deleted.'});
Object.assign(copy.ru,{missingFile:'Файл удалён или недоступен. Добавь его заново.'});
Object.assign(copy.en,{missingFile:'This file was removed or is unavailable. Add it again.'});
const initData = tg?.initData || '';
Object.assign(copy.ru,{saveToLibrary:'Сохранить в библиотеку',savingFile:'Сохраняю файл в библиотеку…',storageFull:'В библиотеке недостаточно места для этого файла.',emptyLibraryNote:'Найди трек или сохрани свой аудиофайл из студии.',localSave:'В деморежиме файл можно слушать и обрабатывать. Сохранение доступно после входа из Telegram.',long:'Для обработки здесь выбери исходный файл и готовый микс до 3 минут.',studioFine:'Обработка на твоём устройстве. Исходный файл и готовый WAV — до 3 минут. Скорость меняется вместе с тоном.',demoStudio:'Эффекты обрабатываются на устройстве. Свой файл загружается в библиотеку только по нажатию «Сохранить».'});
Object.assign(copy.en,{saveToLibrary:'Save to library',savingFile:'Saving your audio file…',storageFull:'There is not enough library storage for this file.',emptyLibraryNote:'Find a track or save your audio file from the studio.',localSave:'You can listen and edit in demo mode. Saving files requires Telegram sign-in.',long:'Choose source audio and an exported mix up to 3 minutes for processing here.',studioFine:'Processed on your device. Source audio and exported WAV support up to 3 minutes. Speed changes pitch too.',demoStudio:'Effects run on your device. Your audio is uploaded to the library only when you choose Save.'});

Object.assign(copy.en,{queue:'Play queue',playNext:'Play next',queueAdd:'Add to queue',queueEmpty:'Your queue is empty',queueAdded:'Added to queue',clearQueue:'Clear queue',moveUp:'Move up',moveDown:'Move down',resume:'Continue listening',compare:'Compare original / effects',dry:'Original sound',wet:'Effects on',presets:'Sound recipes',clean:'Original',warm:'Warm',night:'Night drive',bright:'Bright',treble:'Clarity',saveMix:'Save mix to library',mixSaved:'Mix ready in your studio',queueRemove:'Remove from queue'});
Object.assign(copy.ru,{queue:'Очередь',playNext:'Следующим',queueAdd:'В очередь',queueEmpty:'Очередь пуста',queueAdded:'Добавлено в очередь',clearQueue:'Очистить',moveUp:'Выше',moveDown:'Ниже',resume:'Продолжить слушать',compare:'Сравнить до / после',dry:'Оригинал',wet:'Эффекты включены',presets:'Характер звука',clean:'Оригинал',warm:'Тёплый',night:'Ночной драйв',bright:'Яркий',treble:'Чёткость',saveMix:'Микс в библиотеку',mixSaved:'Микс готов в студии',queueRemove:'Убрать из очереди'});

Object.assign(copy.en,{trimStart:'Start - seconds',trimEnd:'End - seconds (0 = full)',fade:'Smooth fade - seconds',invalidTrim:'End must be after the start.'});
Object.assign(copy.ru,{trimStart:'Начало - сек',trimEnd:'Конец - сек (0 = до конца)',fade:'Плавный вход и выход - сек',invalidTrim:'Конец должен быть после начала.'});
Object.assign(copy.en,{resolving:'Checking the recording...',queued:'Waiting for a download worker...',queueTimeout:'The download queue is busy. Try again shortly or choose another recording.',downloadTimeout:'The source took too long to respond. Try another recording.',requestTimeout:'The server did not respond in time. Check your connection and try again.',prepareFailed:'Could not download this recording. Try another search result.'});
Object.assign(copy.ru,{resolving:'Проверяю запись...',queued:'Ожидаю очередь на загрузку...',queueTimeout:'Очередь занята. Попробуй чуть позже или выбери другую запись.',downloadTimeout:'Источник долго не отвечает. Выбери другую запись.',requestTimeout:'Сервер не ответил вовремя. Проверь соединение и повтори.',prepareFailed:'Не удалось загрузить эту запись. Выбери другой результат.'});
Object.assign(copy.en,{makeSound:'Make your sound.',effectRack:'Your effect chain',effectRackNote:'Combine up to 8 effects. They run in the order you select.',delay:'Delay',equalizer:'Presence',mastering:'Mastering',pro_reverb:'Wide reverb',highpass:'High pass',lowpass:'Low pass',reverse:'Reverse',applyMix:'Apply to full track',applyNote:'Choose your effects, then apply them to hear the result.',mixApplied:'Playing your processed mix',preview:'Hear effects - 15 sec'});
Object.assign(copy.ru,{makeSound:'Создай свой звук.',effectRack:'Цепочка эффектов',effectRackNote:'Сочетай до 8 эффектов. Они применяются в порядке выбора.',delay:'Дилей',equalizer:'Присутствие',mastering:'Мастеринг',pro_reverb:'Объёмный реверб',highpass:'Высокие частоты',lowpass:'Низкие частоты',reverse:'Реверс',applyMix:'Применить ко всему треку',applyNote:'Выбери эффекты и нажми Применить, чтобы услышать результат.',mixApplied:'Играет обработанный микс',preview:'Слушать эффекты - 15 сек'});
Object.assign(copy.en,{openDownload:'Open file',iphoneSave:'Use Download. If unavailable, open the file, then Share > Save to Files. The link expires in 10 minutes.',lyrics:'Lyrics',lyricsLoading:'Finding lyrics...',lyricsEmpty:'No lyrics found for this recording.',lyricsChoose:'Choose the matching song',pitch:'Lower / higher sound',pitchNote:'0 = unchanged. Minus lowers the voice; plus raises it. Apply to hear this change.',liveNote:'Reverb, echo, lo-fi and filters play live. Reverse, mastering and volume leveling use Apply.',live:'Live',renderOnly:'Apply',downloadReady:'Your file is ready'});
Object.assign(copy.ru,{openDownload:'Открыть файл',iphoneSave:'Нажми Скачать. Если недоступно: открой файл, затем Поделиться > Сохранить в Файлы. Ссылка действует 10 минут.',lyrics:'Текст песни',lyricsLoading:'Ищу текст...',lyricsEmpty:'Текст для этой записи не найден.',lyricsChoose:'Выбери нужную песню',pitch:'Звук ниже / выше',pitchNote:'0 - без изменений. Минус понижает голос, плюс повышает. Нажми Применить, чтобы услышать.',liveNote:'Реверб, эхо, lo-fi и фильтры слышны сразу. Реверс, мастеринг и ровная громкость - через Применить.',live:'Сразу',renderOnly:'Применить',downloadReady:'Файл готов'});
Object.assign(copy.en,{pitch:'Tone',pitchNote:'0 is original. Minus is lower, plus is higher. Tone does not change the track speed; use Apply to hear it.',speed:'Speed',ambience:'Reverb / echo strength',extractAudio:'Audio from video',links:'From a link',linkTitle:'Paste. Play. Keep.',linkNote:'YouTube, SoundCloud, TikTok and Instagram. Music catalog links find a matching recording.',linkPlaceholder:'Paste a music or video link',audioMode:'Audio MP3',videoMode:'Video MP4',prepareLink:'Prepare',linkBusy:'Preparing your media...',linkFailed:'This link is unavailable. Try another public link or lower video quality.',linkCancel:'Stop',quality:'Video quality',openMediaStudio:'Open in studio',linkLimit:'Public recordings up to 30 minutes and 49 MB. Temporary files expire in 10 minutes.',toneDown:'Lower tone',toneUp:'Higher tone',speedDown:'Slower',speedUp:'Faster',linkExpired:'The temporary file expired. Prepare the link again.'});
Object.assign(copy.ru,{pitch:'Тон',pitchNote:'0 - оригинал. Минус - ниже, плюс - выше. Тон не меняет скорость трека; для прослушивания нажми Применить.',speed:'Скорость',ambience:'Сила реверба / эха',extractAudio:'Аудио из видео',links:'По ссылке',linkTitle:'Вставь. Смотри. Сохраняй.',linkNote:'YouTube, SoundCloud, TikTok и Instagram. Для ссылок музыкальных каталогов ищем подходящую запись.',linkPlaceholder:'Вставь ссылку на музыку или видео',audioMode:'Аудио MP3',videoMode:'Видео MP4',prepareLink:'Подготовить',linkBusy:'Готовлю файл...',linkFailed:'Ссылка недоступна. Попробуй другую публичную ссылку или уменьши качество.',linkCancel:'Остановить',quality:'Качество видео',openMediaStudio:'В студию',linkLimit:'Публичные записи до 30 минут и 49 МБ. Файлы доступны 10 минут.',toneDown:'Тон ниже',toneUp:'Тон выше',speedDown:'Медленнее',speedUp:'Быстрее',linkExpired:'Срок файла истёк. Подготовь ссылку заново.'});
let linkMode=false,linkUrl='',linkType='audio',linkQuality=360,linkBusy=false,linkResult=null,linkController=null,linkAudioResult=null;
Object.assign(copy.en,{studioInvalid:'Check the trim range and effect settings.',linked:'Together',independent:'Independent',linkTone:'Speed + tone',fineTune:'Fine tune effects',equalizer:'5-band EQ',tremolo:'Tremolo',distortion:'Saturation',stereo:'Stereo width',highpass_hz:'Remove lows - Hz',lowpass_hz:'Remove highs - Hz',lofi_hz:'Lo-fi brightness - Hz',delay_ms:'Delay time - ms',feedback:'Repeats',room_s:'Room size - seconds',comp_threshold:'Compressor threshold - dB',comp_ratio:'Compression ratio',comp_attack:'Attack - ms',comp_release:'Release - ms',stereo_width:'Stereo width',tremolo_rate:'Pulse speed - Hz',tremolo_depth:'Pulse depth',drive:'Saturation strength',eq60:'60 Hz - sub bass',eq250:'250 Hz - warmth',eq1000:'1 kHz - mids',eq4000:'4 kHz - clarity',eq12000:'12 kHz - air',sourceUnavailable:'The platform could not provide this recording. Try another version.',mediaTooLarge:'This file exceeds 256 MB. Select lower video quality.',mediaTooLong:'Choose a recording up to 2 hours.',sourceLogin:'This recording requires access on its platform. Try a public recording.',sourceRateLimit:'The platform temporarily limited requests. Try again later.',unsupportedLink:'Paste a supported public music or video link.',fileTooLarge:'Choose an audio file up to 256 MB.',linkLimit:'Public recordings up to 2 hours and 256 MB. Files are temporary.',studioFine:'MP3: source and result up to 2 hours; input up to 256 MB. WAV output up to 512 MB.',iphoneSave:'Use Download or Open file, then Share > Save to Files. This is a temporary link.',linkNote:'YouTube, SoundCloud, TikTok, Instagram, Vimeo and Bandcamp. Spotify, Apple Music and Yandex Music find matching recordings.'});
Object.assign(copy.ru,{studioInvalid:'\u041f\u0440\u043e\u0432\u0435\u0440\u044c \u043e\u0431\u0440\u0435\u0437\u043a\u0443 \u0438 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b \u044d\u0444\u0444\u0435\u043a\u0442\u043e\u0432.',linked:'Вместе',independent:'Независимо',linkTone:'Скорость + тон',fineTune:'Точная настройка эффектов',equalizer:'Эквалайзер - 5 полос',tremolo:'Тремоло',distortion:'Насыщение',stereo:'Стерео',highpass_hz:'Срез низких - Гц',lowpass_hz:'Срез высоких - Гц',lofi_hz:'Яркость lo-fi - Гц',delay_ms:'Время задержки - мс',feedback:'Повторы',room_s:'Размер комнаты - сек',comp_threshold:'Порог компрессора - dB',comp_ratio:'Степень сжатия',comp_attack:'Атака - мс',comp_release:'Восстановление - мс',stereo_width:'Ширина стерео',tremolo_rate:'Скорость пульсации - Гц',tremolo_depth:'Глубина пульсации',drive:'Сила насыщения',eq60:'60 Гц - суббас',eq250:'250 Гц - тепло',eq1000:'1 кГц - середина',eq4000:'4 кГц - чёткость',eq12000:'12 кГц - воздух',sourceUnavailable:'Платформа не отдала эту запись. Попробуй другую версию.',mediaTooLarge:'Файл больше 256 МБ. Уменьши качество видео.',mediaTooLong:'Выбери запись до 2 часов.',sourceLogin:'Эта запись требует доступа на платформе. Попробуй публичную запись.',sourceRateLimit:'Платформа временно ограничила запросы. Попробуй позже.',unsupportedLink:'Вставь публичную ссылку поддерживаемой платформы.',fileTooLarge:'Выбери аудио до 256 МБ.',linkLimit:'Публичные записи до 2 часов и 256 МБ. Файлы временные.',studioFine:'MP3: исходник и результат до 2 часов; вход до 256 МБ. WAV до 512 МБ.',iphoneSave:'Скачай файл или открой его: Поделиться > Сохранить в Файлы. Ссылка временная.',linkNote:'YouTube, SoundCloud, TikTok, Instagram, Vimeo и Bandcamp. Spotify, Apple Music и Яндекс Музыка - поиск подходящей записи.'});
const demo = !initData;
let language = 'ru';
try { language = localStorage.getItem('swidj-language') || tg?.initDataUnsafe?.user?.language_code?.slice(0,2) || 'ru'; } catch {}
if (!copy[language]) language = 'en';
const t = key => copy[language][key] || copy.en[key] || key;
Object.assign(copy.en,{needsTelegram:'Open the app from Telegram to use server processing.',processingNote:'Preview and export process audio on your server. Files are kept in your library only when you choose Save.',speed:'Speed',export:'Download mix',studioFine:'MP3: source and result up to 30 minutes. WAV files up to 96 MB. Preview trim and effects before saving.',long:'Use Telegram sign-in to process longer tracks on your server.',fileTooLarge:'Choose an audio file up to 49 MB.',format:'Export format',pitch:'Pitch - semitones',effect:'Sound effect',none:'No extra effect',reverb:'Reverb',echo:'Echo',lofi:'Lo-fi',normalize:'Level volume',compressor:'Compression',voiceSearch:'Search by voice',recordVoice:'Record voice',stopVoice:'Stop recording',transcribeVoice:'Use these words',voiceNote:'Say the artist, title or sing words you remember. Audio is sent to your server to read the words. Melody-only humming is not supported.',voiceFile:'Choose a voice recording',voiceBusy:'Reading the words...',voiceDenied:'Microphone is unavailable. Allow it in your browser or choose an audio recording.',voiceEmpty:'No clear words found. Try again or type your query.',voiceLimit:'Choose a recording up to 30 seconds and 8 MB.',studioSize:'The file is too large. Try MP3 or a shorter segment.',voiceDemo:'Voice search is available when opened from Telegram.',serverProcessing:'Processing on your server',pitchNote:'Independent pitch and extra effects are applied in Preview, export and saved mixes.',studioTimeout:'Processing took too long. Try a shorter segment.',effectPreview:'Preview effects - 15 sec'});
Object.assign(copy.ru,{needsTelegram:'Открой приложение из Telegram для обработки на сервере.',processingNote:'Пример и экспорт обрабатывают аудио на твоём сервере. В библиотеке файл остаётся только после нажатия Сохранить.',speed:'Скорость',export:'Скачать микс',studioFine:'MP3: исходник и результат до 30 минут. WAV до 96 МБ. Проверь эффекты в примере перед сохранением.',long:'Для длинных треков открой приложение из Telegram.',fileTooLarge:'Выбери аудио до 49 МБ.',format:'Формат',pitch:'Тон - полутоны',effect:'Эффект',none:'Без доп. эффекта',reverb:'Реверберация',echo:'Эхо',lofi:'Lo-fi',normalize:'Ровная громкость',compressor:'Компрессор',voiceSearch:'Поиск голосом',recordVoice:'Записать голос',stopVoice:'Остановить',transcribeVoice:'Распознать слова',voiceNote:'Назови артиста, трек или напой слова. Запись отправится на твой сервер для распознавания слов. Поиск по мелодии без слов не поддерживается.',voiceFile:'Выбрать запись',voiceBusy:'Распознаю слова...',voiceDenied:'Микрофон недоступен. Разреши доступ или выбери запись.',voiceEmpty:'Не удалось разобрать слова. Попробуй ещё раз.',voiceLimit:'Запись до 30 секунд и 8 МБ.',studioSize:'Файл слишком большой. Выбери MP3 или укороти фрагмент.',voiceDemo:'Голосовой поиск доступен в Telegram.',serverProcessing:'Обработка на твоём сервере',pitchNote:'Тон и доп. эффекты слышны в примере, экспорте и сохранённом миксе.',studioTimeout:'Обработка заняла слишком много времени. Выбери фрагмент покороче.',effectPreview:'Пример эффектов - 15 сек'});
let exportFormat=demo?'wav':'mp3',studioPitch=0,studioEffects=[];
let recorder=null,recordStream=null,voiceBlob=null,voiceUrl=null,voiceBusy=false,recordTimer=null,recordPending=false;
Object.assign(copy.en,{"pitch": "Tone", "pitchNote": "Separate: release the slider to hear the new tone after processing. Speed stays unchanged.", "independent": "Separate", "fineTune": "More controls", "simpleEffects": "Everyday effects", "moreEffects": "More effects", "tonePending": "Applying tone...", "resetEffectControls": "Reset effect controls", "compressor": "Even out loud sounds", "highpass": "Less rumble", "lowpass": "Softer highs", "pro_reverb": "Large room", "distortion": "Warm distortion", "tremolo": "Pulsing volume", "stereo": "Wider sound", "comp_threshold": "Start reducing loud sounds - dB", "comp_ratio": "How strongly to reduce", "comp_attack": "Response time - ms", "comp_release": "Return to normal - ms"});
Object.assign(copy.ru,{"pitch": "\u0422\u043e\u043d", "pitchNote": "\u041e\u0442\u0434\u0435\u043b\u044c\u043d\u043e: \u043e\u0442\u043f\u0443\u0441\u0442\u0438 \u043f\u043e\u043b\u0437\u0443\u043d\u043e\u043a \u0438 \u0434\u043e\u0436\u0434\u0438\u0441\u044c \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438. \u0421\u043a\u043e\u0440\u043e\u0441\u0442\u044c \u043e\u0441\u0442\u0430\u043d\u0435\u0442\u0441\u044f \u043f\u0440\u0435\u0436\u043d\u0435\u0439.", "independent": "\u041e\u0442\u0434\u0435\u043b\u044c\u043d\u043e", "fineTune": "\u0411\u043e\u043b\u044c\u0448\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043a", "simpleEffects": "\u041f\u043e\u043f\u0443\u043b\u044f\u0440\u043d\u044b\u0435 \u044d\u0444\u0444\u0435\u043a\u0442\u044b", "moreEffects": "\u0414\u0440\u0443\u0433\u0438\u0435 \u044d\u0444\u0444\u0435\u043a\u0442\u044b", "tonePending": "\u041c\u0435\u043d\u044f\u044e \u0442\u043e\u043d...", "resetEffectControls": "\u0421\u0431\u0440\u043e\u0441\u0438\u0442\u044c \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u044d\u0444\u0444\u0435\u043a\u0442\u043e\u0432", "compressor": "\u0421\u043c\u044f\u0433\u0447\u0438\u0442\u044c \u0433\u0440\u043e\u043c\u043a\u0438\u0435 \u0437\u0432\u0443\u043a\u0438", "highpass": "\u0423\u0431\u0440\u0430\u0442\u044c \u0433\u0443\u043b", "lowpass": "\u0421\u043c\u044f\u0433\u0447\u0438\u0442\u044c \u0432\u0435\u0440\u0445\u0438", "pro_reverb": "\u0411\u043e\u043b\u044c\u0448\u043e\u0439 \u0437\u0430\u043b", "distortion": "\u041b\u0451\u0433\u043a\u0438\u0439 \u043f\u0435\u0440\u0435\u0433\u0440\u0443\u0437", "tremolo": "\u041f\u0443\u043b\u044c\u0441\u0430\u0446\u0438\u044f \u0433\u0440\u043e\u043c\u043a\u043e\u0441\u0442\u0438", "stereo": "\u041e\u0431\u044a\u0451\u043c\u043d\u043e\u0435 \u0441\u0442\u0435\u0440\u0435\u043e"});
Object.assign(copy.en,{"gentleFx": "Gentle", "balancedFx": "Balanced", "strongFx": "Strong", "effectStrength": "Effect strength"});
Object.assign(copy.ru,{"gentleFx": "\u041c\u044f\u0433\u043a\u043e", "balancedFx": "\u0423\u043c\u0435\u0440\u0435\u043d\u043d\u043e", "strongFx": "\u0421\u0438\u043b\u044c\u043d\u043e", "effectStrength": "\u0421\u0438\u043b\u0430 \u044d\u0444\u0444\u0435\u043a\u0442\u0430"});
Object.assign(copy.en,{"moodTitle": "Find your mood", "moodNote": "A starting point for your next discovery.", "moodFocus": "Focus", "moodNight": "After hours", "moodEnergy": "Energy", "moodCalm": "Slow down", "moodFocusNote": "Instrumental / lo-fi", "moodNightNote": "Electronic / night drive", "moodEnergyNote": "Dance / house", "moodCalmNote": "Ambient / acoustic", "resumeMusic": "Back to your music", "resumeTrack": "Continue listening", "heroLabel": "LISTEN. SHAPE. REPEAT.", "hero1": "Your next", "hero2": "sound starts here.", "heroNote": "Find a track. Make it yours. Keep the feeling.", "fresh": "In your rotation", "quickStudio": "Your sound studio", "quickStudioNote": "A new tone. A little warmth. Your signature."});
Object.assign(copy.ru,{"moodTitle": "\u041f\u043e\u0434 \u0442\u0432\u043e\u0451 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u0438\u0435", "moodNote": "\u0421 \u0447\u0435\u0433\u043e \u043d\u0430\u0447\u043d\u0451\u0442\u0441\u044f \u0442\u0432\u043e\u0451 \u043d\u043e\u0432\u043e\u0435 \u043e\u0442\u043a\u0440\u044b\u0442\u0438\u0435?", "moodFocus": "\u0424\u043e\u043a\u0443\u0441", "moodNight": "\u041f\u043e\u0441\u043b\u0435 \u043f\u043e\u043b\u0443\u043d\u043e\u0447\u0438", "moodEnergy": "\u042d\u043d\u0435\u0440\u0433\u0438\u044f", "moodCalm": "\u0412\u044b\u0434\u043e\u0445\u043d\u0438", "moodFocusNote": "\u0418\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u0430\u043b / lo-fi", "moodNightNote": "\u042d\u043b\u0435\u043a\u0442\u0440\u043e\u043d\u0438\u043a\u0430 / \u043d\u043e\u0447\u043d\u043e\u0439 \u0434\u0440\u0430\u0439\u0432", "moodEnergyNote": "\u0422\u0430\u043d\u0446\u044b / house", "moodCalmNote": "\u042d\u043c\u0431\u0438\u0435\u043d\u0442 / \u0430\u043a\u0443\u0441\u0442\u0438\u043a\u0430", "resumeMusic": "\u0422\u0432\u043e\u044f \u043c\u0443\u0437\u044b\u043a\u0430 \u0436\u0434\u0451\u0442", "resumeTrack": "\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u0441\u043b\u0443\u0448\u0430\u0442\u044c", "heroLabel": "\u0421\u041b\u0423\u0428\u0410\u0419. \u041c\u0415\u041d\u042f\u0419. \u041f\u041e\u0412\u0422\u041e\u0420\u042f\u0419.", "hero1": "\u0422\u0432\u043e\u0439 \u043d\u043e\u0432\u044b\u0439", "hero2": "\u0437\u0432\u0443\u043a \u043d\u0430\u0447\u0438\u043d\u0430\u0435\u0442\u0441\u044f \u0437\u0434\u0435\u0441\u044c.", "heroNote": "\u041d\u0430\u0439\u0434\u0438 \u0442\u0440\u0435\u043a. \u0414\u043e\u0431\u0430\u0432\u044c \u0441\u0432\u043e\u0439 \u0445\u0430\u0440\u0430\u043a\u0442\u0435\u0440. \u0421\u043e\u0445\u0440\u0430\u043d\u0438 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u0438\u0435.", "fresh": "\u0422\u0432\u043e\u044f \u0440\u043e\u0442\u0430\u0446\u0438\u044f", "quickStudio": "\u0422\u0432\u043e\u044f \u0441\u0442\u0443\u0434\u0438\u044f \u0437\u0432\u0443\u043a\u0430", "quickStudioNote": "\u041d\u043e\u0432\u044b\u0439 \u0442\u043e\u043d, \u043d\u0435\u043c\u043d\u043e\u0433\u043e \u0442\u0435\u043f\u043b\u0430, \u0442\u0432\u043e\u0439 \u043f\u043e\u0447\u0435\u0440\u043a."});
Object.assign(copy.en,{"pitchNote": "Separate tone: release to hear a 15-second sample. Apply or Download processes the full track.", "tonePending": "Preparing a short tone sample..."});
Object.assign(copy.ru,{"pitchNote": "\u041e\u0442\u0434\u0435\u043b\u044c\u043d\u044b\u0439 \u0442\u043e\u043d: \u043e\u0442\u043f\u0443\u0441\u0442\u0438 \u043f\u043e\u043b\u0437\u0443\u043d\u043e\u043a \u0434\u043b\u044f \u043f\u0440\u0438\u043c\u0435\u0440\u0430 \u043d\u0430 15 \u0441\u0435\u043a\u0443\u043d\u0434. \u041f\u043e\u043b\u043d\u044b\u0439 \u0442\u0440\u0435\u043a \u2014 \u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c \u0438\u043b\u0438 \u0421\u043a\u0430\u0447\u0430\u0442\u044c.", "tonePending": "\u0413\u043e\u0442\u043e\u0432\u043b\u044e \u043a\u043e\u0440\u043e\u0442\u043a\u0438\u0439 \u043f\u0440\u0438\u043c\u0435\u0440 \u0442\u043e\u043d\u0430..."});
Object.assign(copy.en,{"diskSpace": "There is not enough temporary storage on the host. Try a smaller file or lower quality.", "linkLimit": "", "linkNote": "YouTube, SoundCloud, TikTok and Instagram. Spotify, Apple Music and Yandex Music find matching recordings.", "unsupportedLink": "Paste a supported music or video link."});
Object.assign(copy.ru,{"diskSpace": "\u041d\u0430 \u043a\u043e\u043c\u043f\u044c\u044e\u0442\u0435\u0440\u0435 \u043d\u0435 \u0445\u0432\u0430\u0442\u0430\u0435\u0442 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e\u0433\u043e \u043c\u0435\u0441\u0442\u0430. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u043c\u0435\u043d\u044c\u0448\u0438\u0439 \u0444\u0430\u0439\u043b \u0438\u043b\u0438 \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u043e \u043d\u0438\u0436\u0435.", "linkLimit": "", "linkNote": "YouTube, SoundCloud, TikTok \u0438 Instagram. Spotify, Apple Music \u0438 \u042f\u043d\u0434\u0435\u043a\u0441 \u041c\u0443\u0437\u044b\u043a\u0430 \u2014 \u043f\u043e\u0438\u0441\u043a \u043f\u043e\u0434\u0445\u043e\u0434\u044f\u0449\u0435\u0439 \u0437\u0430\u043f\u0438\u0441\u0438.", "unsupportedLink": "\u0412\u0441\u0442\u0430\u0432\u044c \u0441\u0441\u044b\u043b\u043a\u0443 \u043d\u0430 \u043c\u0443\u0437\u044b\u043a\u0443 \u0438\u043b\u0438 \u0432\u0438\u0434\u0435\u043e."});
Object.assign(copy.en,{"sourceLive": "This broadcast is still live. Send its recording after it ends.", "mediaTooLarge": "This file is too large for this operation. Try MP3 or lower video quality.", "mediaTooLong": "This operation needs a shorter audio segment."});
Object.assign(copy.ru,{"sourceLive": "\u0422\u0440\u0430\u043d\u0441\u043b\u044f\u0446\u0438\u044f \u0435\u0449\u0451 \u0438\u0434\u0451\u0442. \u041e\u0442\u043f\u0440\u0430\u0432\u044c \u0435\u0451 \u0437\u0430\u043f\u0438\u0441\u044c \u043f\u043e\u0441\u043b\u0435 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0438\u044f.", "mediaTooLarge": "\u0424\u0430\u0439\u043b \u0441\u043b\u0438\u0448\u043a\u043e\u043c \u0431\u043e\u043b\u044c\u0448\u043e\u0439 \u0434\u043b\u044f \u044d\u0442\u043e\u0439 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 MP3 \u0438\u043b\u0438 \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u043e \u0432\u0438\u0434\u0435\u043e \u043d\u0438\u0436\u0435.", "mediaTooLong": "\u0414\u043b\u044f \u044d\u0442\u043e\u0439 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438 \u043d\u0443\u0436\u0435\u043d \u0444\u0440\u0430\u0433\u043c\u0435\u043d\u0442 \u043f\u043e\u043a\u043e\u0440\u043e\u0447\u0435."});
Object.assign(copy.en,{"downloadVideo": "Download video MP4", "downloadAudio": "Download audio MP3", "downloadFile": "Download file", "getVideo": "Prepare video MP4", "getAudio": "Prepare audio MP3", "videoShortcut": "Video from a link", "audioShortcut": "Music from a link", "downloadShortcutNote": "Paste a link. Choose your format.", "expandVideo": "Expand video", "newLink": "Another link", "mediaPreparing": "Preparing your file. You can cancel at any time."});
Object.assign(copy.ru,{"downloadVideo": "\u0421\u043a\u0430\u0447\u0430\u0442\u044c \u0432\u0438\u0434\u0435\u043e MP4", "downloadAudio": "\u0421\u043a\u0430\u0447\u0430\u0442\u044c \u0430\u0443\u0434\u0438\u043e MP3", "downloadFile": "\u0421\u043a\u0430\u0447\u0430\u0442\u044c \u0444\u0430\u0439\u043b", "getVideo": "\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c \u0432\u0438\u0434\u0435\u043e MP4", "getAudio": "\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c \u0430\u0443\u0434\u0438\u043e MP3", "videoShortcut": "\u0412\u0438\u0434\u0435\u043e \u043f\u043e \u0441\u0441\u044b\u043b\u043a\u0435", "audioShortcut": "\u041c\u0443\u0437\u044b\u043a\u0430 \u043f\u043e \u0441\u0441\u044b\u043b\u043a\u0435", "downloadShortcutNote": "\u0412\u0441\u0442\u0430\u0432\u044c \u0441\u0441\u044b\u043b\u043a\u0443. \u0412\u044b\u0431\u0435\u0440\u0438 \u0444\u043e\u0440\u043c\u0430\u0442.", "expandVideo": "\u041d\u0430 \u0432\u0435\u0441\u044c \u044d\u043a\u0440\u0430\u043d", "newLink": "\u0414\u0440\u0443\u0433\u0430\u044f \u0441\u0441\u044b\u043b\u043a\u0430", "mediaPreparing": "\u0413\u043e\u0442\u043e\u0432\u043b\u044e \u0444\u0430\u0439\u043b. \u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0443 \u043c\u043e\u0436\u043d\u043e \u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c."});
Object.assign(copy.en,{"recognitionTitle": "Identify music", "recognitionNote": "Choose a clean recording or record at least12 seconds of playing music. Best with full tracks; humming is not supported.", "recordMusic": "Record music", "recognitionFile": "Choose audio file", "recognizeMusic": "Identify recording", "recognizingMusic": "Comparing the recording...", "recognitionEmpty": "No reliable match. Try a longer, clearer recording or the original audio file.", "recognitionLimit": "Choose audio up to32 MB, at least12 seconds long.", "recognitionUnavailable": "Music identification is temporarily unavailable. Try again later.", "recognitionPrivacy": "Only an audio fingerprint is sent to AcoustID.", "recognitionMatches": "Possible matches"});
Object.assign(copy.ru,{"recognitionTitle": "\u0423\u0437\u043d\u0430\u0442\u044c \u043c\u0443\u0437\u044b\u043a\u0443", "recognitionNote": "\u0412\u044b\u0431\u0435\u0440\u0438 \u0447\u0438\u0441\u0442\u0443\u044e \u0437\u0430\u043f\u0438\u0441\u044c \u0438\u043b\u0438 \u0437\u0430\u043f\u0438\u0448\u0438 \u043c\u0443\u0437\u044b\u043a\u0443 \u043d\u0435 \u043a\u043e\u0440\u043e\u0447\u0435 12 \u0441\u0435\u043a\u0443\u043d\u0434. \u041b\u0443\u0447\u0448\u0435 \u0441 \u043f\u043e\u043b\u043d\u044b\u043c \u0442\u0440\u0435\u043a\u043e\u043c; \u043d\u0430\u043f\u0435\u0432\u0430\u043d\u0438\u0435 \u043d\u0435 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0435\u0442\u0441\u044f.", "recordMusic": "\u0417\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u043c\u0443\u0437\u044b\u043a\u0443", "recognitionFile": "\u0412\u044b\u0431\u0440\u0430\u0442\u044c \u0430\u0443\u0434\u0438\u043e\u0444\u0430\u0439\u043b", "recognizeMusic": "\u041e\u043f\u0440\u0435\u0434\u0435\u043b\u0438\u0442\u044c \u0437\u0430\u043f\u0438\u0441\u044c", "recognizingMusic": "\u0421\u0440\u0430\u0432\u043d\u0438\u0432\u0430\u044e \u0437\u0430\u043f\u0438\u0441\u044c...", "recognitionEmpty": "\u041d\u0435\u0442 \u043d\u0430\u0434\u0451\u0436\u043d\u043e\u0433\u043e \u0441\u043e\u0432\u043f\u0430\u0434\u0435\u043d\u0438\u044f. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u0437\u0430\u043f\u0438\u0441\u044c \u043f\u043e\u0447\u0438\u0449\u0435 \u0438\u043b\u0438 \u043e\u0440\u0438\u0433\u0438\u043d\u0430\u043b\u044c\u043d\u044b\u0439 \u0430\u0443\u0434\u0438\u043e\u0444\u0430\u0439\u043b.", "recognitionLimit": "\u0412\u044b\u0431\u0435\u0440\u0438 \u0430\u0443\u0434\u0438\u043e \u0434\u043e 32 \u041c\u0411, \u043d\u0435 \u043a\u043e\u0440\u043e\u0447\u0435 12 \u0441\u0435\u043a\u0443\u043d\u0434.", "recognitionUnavailable": "\u041e\u043f\u0440\u0435\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u043c\u0443\u0437\u044b\u043a\u0438 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u043f\u043e\u0437\u0436\u0435.", "recognitionPrivacy": "\u0412 AcoustID \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442\u0441\u044f \u0442\u043e\u043b\u044c\u043a\u043e \u0437\u0432\u0443\u043a\u043e\u0432\u043e\u0439 \u043e\u0442\u043f\u0435\u0447\u0430\u0442\u043e\u043a.", "recognitionMatches": "\u0412\u043e\u0437\u043c\u043e\u0436\u043d\u044b\u0435 \u0441\u043e\u0432\u043f\u0430\u0434\u0435\u043d\u0438\u044f"});
Object.assign(copy.en,{"recognitionTitle": "Identify music \u00b7 Beta", "recognitionNote": "Choose a recording or record at least12 seconds of playing music. We will identify it and prepare the full track. Replayed or hummed tunes are not supported.", "recognizeMusic": "Identify and get track", "recognitionPrivacy": "AcoustID ? Beta"});
Object.assign(copy.ru,{"recognitionTitle": "\u0423\u0437\u043d\u0430\u0442\u044c \u043c\u0443\u0437\u044b\u043a\u0443 \u00b7 \u0411\u0435\u0442\u0430", "recognitionNote": "\u0412\u044b\u0431\u0435\u0440\u0438 \u0437\u0430\u043f\u0438\u0441\u044c \u0438\u043b\u0438 \u0437\u0430\u043f\u0438\u0448\u0438 \u043c\u0443\u0437\u044b\u043a\u0443 \u043d\u0435 \u043a\u043e\u0440\u043e\u0447\u0435 12 \u0441\u0435\u043a\u0443\u043d\u0434. \u041e\u043f\u0440\u0435\u0434\u0435\u043b\u0438\u043c \u0438 \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u043c \u043f\u043e\u043b\u043d\u044b\u0439 \u0442\u0440\u0435\u043a. \u041d\u0430\u043f\u0435\u0432\u0430\u043d\u0438\u0435 \u0438 \u043f\u0435\u0440\u0435\u0438\u0433\u0440\u0430\u043d\u043d\u0430\u044f \u043c\u0435\u043b\u043e\u0434\u0438\u044f \u043d\u0435 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u044e\u0442\u0441\u044f.", "recognizeMusic": "\u0423\u0437\u043d\u0430\u0442\u044c \u0438 \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0442\u0440\u0435\u043a", "recognitionPrivacy": "AcoustID \u00b7 \u0411\u0435\u0442\u0430"});
Object.assign(copy.en,{"recognitionNote": "Record music or choose an audio file."});
Object.assign(copy.ru,{"recognitionNote": "\u0417\u0430\u043f\u0438\u0448\u0438 \u043c\u0443\u0437\u044b\u043a\u0443 \u0438\u043b\u0438 \u0432\u044b\u0431\u0435\u0440\u0438 \u0430\u0443\u0434\u0438\u043e\u0444\u0430\u0439\u043b."});
Object.assign(copy.en,{"recognitionTooShort": "The recording is too short. Record at least12 seconds.", "recognitionInvalidAudio": "Could not read this recording. Please record again.", "recognitionLimit": "The audio file is larger than32 MB."});
Object.assign(copy.ru,{"recognitionTooShort": "\u0417\u0430\u043f\u0438\u0441\u044c \u0441\u043b\u0438\u0448\u043a\u043e\u043c \u043a\u043e\u0440\u043e\u0442\u043a\u0430\u044f. \u0417\u0430\u043f\u0438\u0448\u0438 \u043d\u0435 \u043c\u0435\u043d\u0435\u0435 12 \u0441\u0435\u043a\u0443\u043d\u0434.", "recognitionInvalidAudio": "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u0440\u043e\u0447\u0438\u0442\u0430\u0442\u044c \u0437\u0430\u043f\u0438\u0441\u044c. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u0437\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u0435\u0449\u0451 \u0440\u0430\u0437.", "recognitionLimit": "\u0410\u0443\u0434\u0438\u043e\u0444\u0430\u0439\u043b \u0431\u043e\u043b\u044c\u0448\u0435 32 \u041c\u0411."});
Object.assign(copy.en,{"charts": "Charts", "chartsTitle": "Popular. Right now.", "chartsNote": "Top 50 songs by country.", "chartSource": "Apple Music Top 50", "chartCountry": "Country", "chartFilter": "Find a song in this chart", "chartUnavailable": "Could not load this chart. Please try again.", "chartNoMatches": "No songs match your filter.", "chartUpdated": "Updated", "chartCached": "Saved chart", "chartOpenSource": "View on Apple Music", "chartHome": "Explore the charts", "chartHomeNote": "The Top50. Choose your country.", "countryDE": "Germany", "countryUS": "United States", "countryGB": "United Kingdom", "countryFR": "France", "countryUA": "Ukraine", "countryRU": "Russia"});
Object.assign(copy.ru,{"charts": "\u0427\u0430\u0440\u0442\u044b", "chartsTitle": "\u0422\u043e, \u0447\u0442\u043e \u0441\u043b\u0443\u0448\u0430\u044e\u0442 \u0441\u0435\u0439\u0447\u0430\u0441.", "chartsNote": "50 \u043f\u043e\u043f\u0443\u043b\u044f\u0440\u043d\u044b\u0445 \u043f\u0435\u0441\u0435\u043d \u043f\u043e \u0441\u0442\u0440\u0430\u043d\u0430\u043c.", "chartSource": "Apple Music Top 50", "chartCountry": "\u0421\u0442\u0440\u0430\u043d\u0430", "chartFilter": "\u041d\u0430\u0439\u0442\u0438 \u043f\u0435\u0441\u043d\u044e \u0432 \u0447\u0430\u0440\u0442\u0435", "chartUnavailable": "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0447\u0430\u0440\u0442. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u0435\u0449\u0451 \u0440\u0430\u0437.", "chartNoMatches": "\u041f\u043e \u044d\u0442\u043e\u043c\u0443 \u0444\u0438\u043b\u044c\u0442\u0440\u0443 \u043f\u0435\u0441\u0435\u043d \u043d\u0435\u0442.", "chartUpdated": "\u041e\u0431\u043d\u043e\u0432\u043b\u0451\u043d", "chartCached": "\u0421\u043e\u0445\u0440\u0430\u043d\u0451\u043d\u043d\u044b\u0439 \u0447\u0430\u0440\u0442", "chartOpenSource": "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0447\u0430\u0440\u0442 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0430", "chartHome": "\u041e\u0442\u043a\u0440\u043e\u0439 \u0447\u0430\u0440\u0442\u044b", "chartHomeNote": "\u0422\u043e\u043f 50. \u0412\u044b\u0431\u0435\u0440\u0438 \u0441\u0442\u0440\u0430\u043d\u0443.", "countryDE": "\u0413\u0435\u0440\u043c\u0430\u043d\u0438\u044f", "countryUS": "\u0421\u0428\u0410", "countryGB": "\u0412\u0435\u043b\u0438\u043a\u043e\u0431\u0440\u0438\u0442\u0430\u043d\u0438\u044f", "countryFR": "\u0424\u0440\u0430\u043d\u0446\u0438\u044f", "countryUA": "\u0423\u043a\u0440\u0430\u0438\u043d\u0430", "countryRU": "\u0420\u043e\u0441\u0441\u0438\u044f"});
const demos = [
  ['Velvet hours','SwiDJ Originals'],['Sunset circuit','SwiDJ Originals'],['After the rain','SwiDJ Originals'],
  ['Blue distance','SwiDJ Originals'],['Soft focus','SwiDJ Originals'],['Golden hour','SwiDJ Originals']
].map(([title,artist], i) => ({id:`demo:${i}`,title,artist,duration:24,kind:'track',playable:true,demo:i}));
let state = {tracks:[],favorites:[],playlists:[],bot:''};
let route = 'home', filter = 'all', playlist = null, current = null, results = null, searching = false, failed = false;
let trackBlob = null, trackUrl = null, previewUrl = null, loadingTrack = 0, toastTimer;
let renderBusy = false, refreshing = false, sourceDuration = 0;
let preparation = null, searchQuery = '';
let lastRendered=null;
function studioSignature(){return JSON.stringify([loadingTrack,engine.bass,engine.speed,engine.treble,studioPitch,studioEffects,engine.trimStart,engine.trimEnd,engine.fade,engine.ambience,engine.linked,engine.params]);}
function invalidateMix(){const resume=engine.processed?previewStart+audio.currentTime*engine.speed:audio.currentTime;lastRendered=null;engine.setProcessed(false);if(previewUrl&&trackUrl){audio.src=trackUrl;audio.currentTime=resume;URL.revokeObjectURL(previewUrl);previewUrl=null;engine.setProcessed(false);engine.setBass(engine.bass);engine.setSpeed(engine.speed);}}
let playQueue=[], playHistory=[], restoredTracks=[], resumeState=null, lastPositionSave=0;
const sessionKey='swidj-session-v1-'+(demo?'demo':String(tg?.initDataUnsafe?.user?.id||'unknown'));
try {const saved=JSON.parse(localStorage.getItem(sessionKey)||'null');if(saved){resumeState=saved.resume;restoredTracks=Array.isArray(saved.tracks)?saved.tracks.slice(0,101):[];playQueue=Array.isArray(saved.queue)?saved.queue.filter(x=>typeof x==='string').slice(0,100):[];}}catch{}
function persistSession(){try{localStorage.setItem(sessionKey,JSON.stringify({tracks:[...new Set([...playQueue,current?.id])].map(trackById).filter(x=>x&&!x.local).slice(0,101).map(x=>({id:x.id,title:x.title,artist:x.artist,duration:x.duration,kind:x.kind,playable:x.playable,demo:x.demo})),queue:playQueue.filter(id=>!id.startsWith('local:')),resume:current&&!current.local?{id:current.id,position:previewUrl?0:audio.currentTime}:resumeState}));}catch{}}
function queueDialog(){dialog(t('queue'),playQueue.length?playQueue.map((id,index)=>{const track=trackById(id);return track?`<div class="queue-row"><span><strong>${e(track.title)}</strong><small>${e(track.artist)}</small></span><button type="button" class="icon-btn" data-q-up="${index}" aria-label="${e(t('moveUp'))}" ${index===0?'disabled':''}>&uarr;</button><button type="button" class="icon-btn" data-q-down="${index}" aria-label="${e(t('moveDown'))}" ${index===playQueue.length-1?'disabled':''}>&darr;</button><button type="button" class="icon-btn" data-q-remove="${index}" aria-label="${e(t('queueRemove'))}">&times;</button></div>`:'';}).join(''):`<p>${e(t('queueEmpty'))}</p>`,`<button type="button" class="btn secondary" id="clear-queue">${e(t('clearQueue'))}</button>`);}

const extraTracks = new Map(restoredTracks.filter(x=>x&&typeof x.id==='string'&&typeof x.title==='string'&&typeof x.artist==='string'&&(!demo||demos.some(d=>d.id===x.id&&d.demo===x.demo))).map(x=>[x.id,x]));
const localTracks = new Map();
const audio = $('audio'), engine = new AudioEngine(audio);
audio.volume = .8;
let demoState;
try { demoState = JSON.parse(localStorage.getItem('swidj-demo-library') || 'null'); } catch {}
const api = async (path, payload) => {
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
  let response;try {response = await fetch('/api/' + path, {method:payload ? 'POST':'GET', headers:{'X-Telegram-Init-Data':initData,...(payload ? {'Content-Type':'application/json'}:{})},body:payload ? JSON.stringify(payload):undefined, credentials:'omit',signal:controller.signal});}catch(error){if(error.name==='AbortError')throw new Error('requestTimeout');throw error;}finally{clearTimeout(timer);}
  if (!response.ok) throw new Error(({401:'expired',403:'unavailable',409:'capacity',410:'missingFile',429:'rateLimit',503:'unavailable'})[response.status] || 'error');
  return response;
};
function toast(key) { $('toast').textContent = t(key); $('toast').classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(()=>$('toast').classList.remove('show'),4500); }
function report(error) { toast(copy.en[error?.message] ? error.message : 'error'); }
function liked(track) { return state.favorites.includes(track.id); }
function trackById(id) { return [...(current?[current]:[]),...state.tracks,...(state.recent || []),...(results || []),...localTracks.values(),...extraTracks.values()].find(s=>s.id===id); }
function color(track) { return track.demo ?? [...track.id].reduce((n,c)=>n+c.charCodeAt(0),0)%6; }
function art(track, small=false) {
  const index = color(track);
  const cover = track.cover ? `<img class="cover-image" src="${e(track.cover)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '';
  return small ? `<span class="mini-art art-${index}" aria-hidden="true">${cover}♪</span>` : `<span class="art art-${index}">${cover}<span class="art-corner">${e(track.artist || 'SwiDJ')}</span><span class="art-symbol" aria-hidden="true">${['◒','◓','∿','◌','◍','≋'][index]}</span><span class="card-play">${icon('play')}</span></span>`;
}
function card(track) { return `<article class="music-card"><button class="art-button" data-track="${e(track.id)}" data-action="play" aria-label="${e(t('play')+' '+track.title)}">${art(track)}</button><span class="card-title">${e(track.title)}</span><div class="card-meta"><span class="card-artist">${e(track.artist)}</span><button class="icon-btn" data-track="${e(track.id)}" data-action="like" aria-label="${e(t('favorite'))}" aria-pressed="${liked(track)}">${icon('heart')}</button></div></article>`; }
function row(track) { return `<article class="track-row ${current?.id===track.id?'current':''}"><button class="icon-btn" data-track="${e(track.id)}" data-action="play" aria-label="${e(t('play'))}">${art(track,true)}</button><button class="track-copy plain" data-track="${e(track.id)}" data-action="play"><strong>${e(track.title)}</strong><small>${e(track.artist)}</small></button><span class="track-time">${stamp(track.duration)}</span><button class="icon-btn" data-track="${e(track.id)}" data-action="like" aria-label="${e(t('favorite'))}" aria-pressed="${liked(track)}">${icon('heart')}</button><button class="icon-btn" data-track="${e(track.id)}" data-action="menu" aria-label="${e(t('more'))}">${icon('more')}</button></article>`; }
function empty(title, note, name='music') { return `<div class="empty">${icon(name)}<strong>${e(t(title))}</strong><p>${e(t(note))}</p></div>`; }
function heading(title, note) { return `<div class="page-heading"><p class="eyebrow">${e(t(route))}</p><h1>${e(t(title))}</h1><p>${e(t(note))}</p></div>`; }
function note() { return demo ? `<p class="demo-note">${icon('info')}${e(t('demoNote'))}</p>` : ''; }
function mediaShortcuts(){return `<div class="media-shortcuts">${['video','audio'].map(mode=>`<button type="button" class="media-shortcut" data-media-mode="${mode}">${icon(mode==='video'?'play':'download')}<span><strong>${e(t(mode==='video'?'videoShortcut':'audioShortcut'))}</strong><small>${e(t('downloadShortcutNote'))}</small></span></button>`).join('')}</div>`;}
let chartCountry='de',chartData=null,chartsLoading=false,chartsError=false,chartFilter='',chartRequest=0,chartBusy=null;
const chartResolved=new Map(),chartCountries=['de','us','gb','fr','ua','ru'];
try{const saved=localStorage.getItem('swidj-chart-country');if(chartCountries.includes(saved))chartCountry=saved;}catch{}
function chartKey(item){return chartCountry+':'+item.id;}
function chartRows(){
 const filter=chartFilter.toLocaleLowerCase().trim();
 const entries=(chartData?.tracks||[]).map((track,index)=>({track,index})).filter(({track})=>(track.title+' '+track.artist).toLocaleLowerCase().includes(filter));
 return entries.length?entries.map(({track,index})=>{const key=chartKey(track),ready=chartResolved.get(key);return `<article class="chart-row ${current?.id===ready?.id?'current':''}"><span class="chart-rank">${track.rank}</span><button type="button" class="chart-song plain" data-chart-play="${index}"><span class="chart-art">${track.artwork?`<img class="cover-image" src="${e(track.artwork)}" alt="" loading="lazy" decoding="async">`:icon('music')}</span><span><strong>${e(track.title)}</strong><small>${e(track.artist)}</small></span></button><button type="button" class="icon-btn" data-chart-play="${index}" aria-label="${e(t('play')+' '+track.title)}" ${chartBusy?'disabled':''}>${chartBusy===key?'<span class="activity-spinner"></span>':icon('play')}</button>${ready?`<button type="button" class="icon-btn" data-track="${e(ready.id)}" data-action="menu" aria-label="${e(t('more'))}">${icon('more')}</button>`:''}</article>`;}).join(''):`<p class="chart-empty">${e(t('chartNoMatches'))}</p>`;
}
function chartsScreen(){
 const date=new Date(chartData?.updated||'');
 return `<section class="chart-hero"><p class="eyebrow">SWIDJ / TOP 50</p><h1>${e(t('chartsTitle'))}</h1><p>${e(t('chartsNote'))}</p><span class="chart-hero-mark" aria-hidden="true">50</span></section><div class="chart-toolbar"><label>${e(t('chartCountry'))}<select id="chart-country">${chartCountries.map(country=>`<option value="${country}" ${chartCountry===country?'selected':''}>${e(t('country'+country.toUpperCase()))}</option>`).join('')}</select></label><button type="button" class="btn secondary" id="refresh-charts" ${chartsLoading?'disabled':''}>${icon('repeat')}${e(t('refresh'))}</button></div>${demo?`<p class="chart-empty">${e(t('needsTelegram'))}</p>`:chartsLoading?`<div class="loading" role="status">${e(t('loading'))}</div>`:chartsError?`<p class="chart-empty" role="status">${e(t('chartUnavailable'))}</p>`:chartData?`<div class="chart-source"><strong>${e(t('chartSource'))}</strong><span>${Number.isFinite(date.getTime())?e(t('chartUpdated')+' '+date.toLocaleDateString(language==='ru'?'ru-RU':'en-GB')):''}${chartData.stale?' / '+e(t('chartCached')):''}</span></div><input id="chart-filter" type="search" maxlength="80" value="${e(chartFilter)}" placeholder="${e(t('chartFilter'))}" aria-label="${e(t('chartFilter'))}"><section id="chart-tracks" class="chart-list">${chartRows()}</section><a class="chart-credit" href="${e(chartData.source_url)}" target="_blank" rel="noopener noreferrer">${e(t('chartOpenSource'))} &#8599;</a>`:''}`;
}
async function loadCharts(){
 if(demo)return;const request=++chartRequest,country=chartCountry;chartsLoading=true;chartsError=false;if(route==='charts')render();
 try{const response=await api('charts?country='+country);const data=await response.json();if(request===chartRequest)chartData=data;}
 catch{if(request===chartRequest){chartsError=true;chartData=null;}}
 finally{if(request===chartRequest){chartsLoading=false;if(route==='charts')render();}}
}
async function playChart(index){
 if(chartBusy)return;const item=chartData?.tracks[Number(index)];if(!item)return;
 const key=chartKey(item);chartBusy=key;render();
 try{
  // Unlock audio during the original tap, before waiting for search/network.
  await engine.unlock();
  const cached=chartResolved.get(key);let candidates=cached?[cached]:null;
  if(!candidates){
   let response;
   try{response=await api('search?q='+encodeURIComponent(item.query));}
   catch(error){if(error.message!=='rateLimit')throw error;await new Promise(resolve=>setTimeout(resolve,3200));response=await api('search?q='+encodeURIComponent(item.query));}
   const tracks=(await response.json()).tracks||[];candidates=matchingRecordings(item,tracks).slice(0,2);
   if(!candidates.length){searchQuery=item.query;results=tracks;linkMode=false;navigate('search');return;}
  }
  let lastError;
  for(const recording of candidates){
   extraTracks.set(recording.id,recording);
   try{if(await playTrack(recording))chartResolved.set(key,recording);return;}
   catch(error){
    lastError=error;chartResolved.delete(key);
    if(!['prepareFailed','sourceUnavailable','sourceLogin','sourceRateLimit','invalidAudio'].includes(error.message)&&error.name!=='NotSupportedError')throw error;
   }
  }
  if(lastError)throw lastError;
 }catch(error){report(error);}finally{chartBusy=null;if(route==='charts')render();}
}

function home() {
  const tracks = [...new Map([...(state.recent || []),...state.tracks].map(s=>[s.id,s])).values()].slice(0,4);
  return `<section class="hero"><div class="hero-copy"><p class="eyebrow">${e(t('heroLabel'))}</p><h1>${e(t('hero1'))}<br><em>${e(t('hero2'))}</em></h1><p>${e(t('heroNote'))}</p><button class="btn" data-go="search">${icon('search')}${e(t('findMusic'))}</button><button type="button" class="text-btn hero-link" data-open-links>${e(t('links'))} &#8599;</button></div><div class="hero-disc" aria-hidden="true"></div><span class="hero-tag"><i></i>${e(t('yourSound'))}</span></section><button type="button" class="chart-spotlight" data-go="charts">${icon('charts')}<span><strong>${e(t('chartHome'))}</strong><small>${e(t('chartHomeNote'))}</small></span><b aria-hidden="true">50 &#8599;</b></button>${mediaShortcuts()}<div class="section-head"><div><h2>${e(t(demo?'continue':'fresh'))}</h2><p>${e(t(demo?'continueNote':'freshNote'))}</p></div><button class="text-btn" data-go="library">${e(t('allMusic'))}</button></div>${tracks.length?`<div class="card-grid">${tracks.map(card).join('')}</div>`:empty('emptyLibrary','emptyLibraryNote')}<div class="quick-grid"><button class="quick-card" data-go="studio"><span class="quick-icon">${icon('studio')}</span><span><strong>${e(t('quickStudio'))}</strong><small>${e(t('quickStudioNote'))}</small></span>${icon('arrow').replace('<svg','<svg class="arrow"')}</button><button class="quick-card" data-go="library"><span class="quick-icon">${icon('library')}</span><span><strong>${e(t('quickLibrary'))}</strong><small>${e(t('quickLibraryNote'))}</small></span>${icon('arrow').replace('<svg','<svg class="arrow"')}</button></div>${note()}`;
}
let recognitionBlob=null,recognitionUrl=null,recognitionBusy=false,recognitionMatches=null,recognitionTrack=null;
function setRecognition(blob){recognitionBlob=blob;recognitionMatches=null;recognitionTrack=null;if(recognitionUrl)URL.revokeObjectURL(recognitionUrl);recognitionUrl=URL.createObjectURL(blob);}
function musicWords(text){return String(text).normalize('NFKC').toLocaleLowerCase().match(/[\p{L}\p{N}]+/gu)||[];}
function matchingRecordings(match,tracks){const title=musicWords(match.title).filter(x=>x.length>1),artist=musicWords(match.artist).filter(x=>x.length>1);return tracks.filter(track=>{const words=new Set(musicWords(track.title+' '+track.artist));return title.length&&artist.length&&title.every(x=>words.has(x))&&artist.every(x=>words.has(x));});}
function matchingRecording(match,tracks){return matchingRecordings(match,tracks)[0];}
function recognitionPanel(){return `<details class="recognition-panel"><summary>${e(t('recognitionTitle'))}</summary><p>${e(t('recognitionNote'))}</p><div class="voice-actions"><button type="button" class="btn secondary" id="record-music" ${recognitionBusy?'disabled':''}>${e(t(recorder?.state==='recording'?'stopVoice':'recordMusic'))}</button><label class="btn secondary" for="recognition-file">${e(t('recognitionFile'))}</label><input id="recognition-file" type="file" accept="audio/*"></div>${recognitionUrl?`<audio controls src="${e(recognitionUrl)}"></audio><button type="button" class="btn" id="recognize-music" ${recognitionBusy||recorder?.state==='recording'?'disabled':''}>${e(t(recognitionBusy?'recognizingMusic':'recognizeMusic'))}</button>`:''}${recognitionTrack?`<section class="recognition-ready"><strong>${e(recognitionTrack.title)}</strong><span>${e(recognitionTrack.artist)}</span><button type="button" class="btn" data-track="${e(recognitionTrack.id)}" data-action="download">${icon('download')}${e(t('downloadAudio'))}</button><button type="button" class="btn secondary" data-track="${e(recognitionTrack.id)}" data-action="send">${e(t('send'))}</button></section>`:''}${recognitionMatches!==null&&!recognitionTrack?`<section class="recognition-results"><h3>${e(t(recognitionMatches.length?'recognitionMatches':'recognitionEmpty'))}</h3>${recognitionMatches.map((match,i)=>`<button type="button" class="dialog-option" data-recognition-match="${i}">${icon('search')}<span><strong>${e(match.title)}</strong><small>${e(match.artist)}</small></span></button>`).join('')}</section>`:''}</details>`;}
async function identifyMusic(){
 if(demo)return toast('needsTelegram');if(recognitionBusy||!recognitionBlob)return;
 if(recognitionBlob.size>32*1024**2)return toast('recognitionLimit');
 recognitionBusy=true;render();document.querySelector('.recognition-panel').open=true;
 try{
  await engine.unlock();
  const form=new FormData();form.append('file',recognitionBlob,'recording.audio');
  const response=await fetch('/api/recognize',{method:'POST',headers:{'X-Telegram-Init-Data':initData},body:form,credentials:'omit'});
  if(!response.ok){let reason;try{reason=(await response.json()).reason;}catch{}throw new Error(copy.en[reason]?reason:({400:'recognitionInvalidAudio',413:'recognitionLimit',401:'expired',429:'rateLimit',503:'recognitionUnavailable',504:'studioTimeout'})[response.status]||'recognitionUnavailable');}
  recognitionMatches=(await response.json()).matches||[];
  if(recognitionMatches.length){
   const match=recognitionMatches[0],tracks=(await(await api('search?q='+encodeURIComponent(match.query))).json()).tracks||[];
   const recording=matchingRecording(match,tracks);
   if(recording){extraTracks.set(recording.id,recording);if(await playTrack(recording))recognitionTrack=recording;}
  }
 }catch(error){report(error);}finally{recognitionBusy=false;if(route==='search'){render();document.querySelector('.recognition-panel').open=true;}}
}
function searchScreen() {
  const tabs=`<div class="search-tabs"><button type="button" data-search-tab="music" aria-pressed="${!linkMode}">${e(t('search'))}</button><button type="button" data-search-tab="links" aria-pressed="${linkMode}">${e(t('links'))}</button></div>`;
  if(linkMode)return tabs+linkScreen();
  return tabs+heading('searchTitle','searchNote')+`<form id="search-form" class="search-form">${icon('search')}<input id="search-input" type="search" value="${e(searchQuery)}" maxlength="120" minlength="2" placeholder="${e(t('searchPlaceholder'))}" aria-label="${e(t('searchPlaceholder'))}" required><button class="btn" ${searching?'disabled':''}>${e(t('searchButton'))}</button></form>${demo?`<p class="demo-note">${icon('info')}${e(t('demoSearch'))}</p>`:''}${recognitionPanel()}<details class="voice-panel"><summary>${e(t('voiceSearch'))}</summary><p>${e(t('voiceNote'))}</p><div class="voice-actions"><button type="button" class="btn secondary" id="record-voice">${e(t(recorder?.state==='recording'?'stopVoice':'recordVoice'))}</button><label class="btn secondary" for="voice-file">${e(t('voiceFile'))}</label><input id="voice-file" type="file" accept="audio/*"></div>${voiceUrl?`<audio controls src="${e(voiceUrl)}"></audio><button type="button" class="btn" id="transcribe-voice" ${voiceBusy?'disabled':''}>${e(t(voiceBusy?'voiceBusy':'transcribeVoice'))}</button>`:''}</details><div class="section-head"><h2>${e(t('results'))}</h2></div>${searching?`<div class="loading" role="status">${e(t('searching'))}</div>`:results===null?empty('searchEmpty','searchHint','search'):results.length?`<div class="track-list">${results.map(row).join('')}</div>`:empty('noResults','retrySearch','search')}`;
}
function libraryScreen() {
  const selected = state.playlists.find(p=>p.id===playlist);
  let tracks = state.tracks;
  if (selected) tracks = selected.tracks.map(trackById).filter(Boolean);
  else if (filter==='favorites') tracks=tracks.filter(liked);
  else if (filter==='uploads') tracks=tracks.filter(s=>s.kind==='upload');
  const chips = ['all','favorites','uploads','playlists'].map(key=>
    `<button class="chip ${filter===key&&!selected?'active':''}" data-filter="${key}">${e(t(key))}</button>`).join('');
  let body;
  if (filter === 'playlists' && !selected) {
    const folders = state.playlists.map(p=>
      `<button class="playlist-card" data-playlist="${e(p.id)}">${icon('folder')}<span><strong>${e(p.name)}</strong><small>${p.tracks.length} ${e(t('tracks'))}</small></span></button>`).join('');
    body = `<div class="section-head"><h2>${e(t('playlists'))}</h2><button class="text-btn" id="new-playlist">+ ${e(t('newPlaylist'))}</button></div><div class="playlist-grid">${folders}</div>`;
    if (!state.playlists.length) body += empty('emptyPlaylist','emptyPlaylistNote','folder');
  } else {
    const action = selected
      ? `<span class="playlist-tools"><button class="icon-btn" id="playlist-settings" aria-label="${e(t('more'))}">${icon('more')}</button><button class="text-btn" id="back-playlists">${e(t('back'))}</button></span>`
      : `<span class="playlist-tools"><button class="icon-btn" id="refresh-library" aria-label="${e(t('refresh'))}">${icon('repeat')}</button><button class="text-btn" id="new-playlist">+ ${e(t('newPlaylist'))}</button></span>`;
    body = `<div class="section-head"><h2>${e(selected?.name || t(filter))} <span class="count">${tracks.length}</span></h2>${action}</div>`;
    body += tracks.length
      ? `<div class="track-list">${tracks.map(row).join('')}</div>`
      : empty(selected?'emptyPlaylist':'emptyLibrary',selected?'emptyPlaylistNote':'emptyLibraryNote');
  }
  return heading('libraryTitle','libraryNote') + `<div class="chips">${chips}</div>` + body + note();
}

const bassOptions = [[-6,'bassLess'],[0,'bassOff'],[3,'bassGentle'],[6,'bassMedium'],[9,'bassStrong']];
function studio() {
  return `<section class="studio-hero"><div><p class="eyebrow">SwiDJ / STUDIO</p><h1>${e(t('makeSound'))}</h1><p>${e(t('studioNote'))}</p></div><div class="studio-visual" aria-hidden="true"><div class="visual-orbit"></div><svg class="visual-wave" viewBox="0 0 300 120">${[20,40,65,30,80,100,55,35,75,90,45,65,25,50,30].map((h,i)=>`<rect x="${i*20}" y="${60-h/2}" width="8" height="${h}" rx="4"/>`).join('')}</svg><span>01 / SOUND LAB</span></div></section>`+`<div class="studio-layout"><section class="studio-source">${current?art(current):`<div class="art art-0"><span class="art-symbol">∿</span></div>`}<h2>${e(current?.title || t('chooseFirst'))}</h2><p>${e(current?.artist || t('chooseFirstNote'))}</p><label class="btn secondary" for="local-file">${icon('upload')}${e(t('chooseFile'))}</label><input id="local-file" type="file" accept="audio/*,.mp3,.wav,.ogg,.m4a,.flac"></section><section class="studio-controls"><span class="studio-badge">${e(t(demo?'localProcessing':'serverProcessing'))}</span><h2>${e(t('soundSettings'))}</h2><p>${e(t('applyNote'))}</p><p class="output-state">${e(t(previewUrl?'mixApplied':'dry'))}</p><div class="control-label"><label>${e(t('bass'))}</label><output id="bass-value">${engine.bass>0?'+':''}${engine.bass} dB</output></div><div class="bass-options">${bassOptions.map(([value,label])=>`<button class="chip ${value===engine.bass?'active':''}" data-bass="${value}" aria-pressed="${value===engine.bass}">${e(t(label))}</button>`).join('')}</div><div class="control-label"><label for="speed">${e(t('speed'))}</label><output id="speed-value">${engine.speed.toFixed(2)}×</output></div><input id="speed" class="control-range" type="range" min="0.5" max="2" step="0.05" value="${engine.speed}"><div class="range-labels"><span>${e(t('slower'))}</span><span>${e(t('original'))}</span><span>${e(t('faster'))}</span></div><button class="btn secondary" id="preview-mix" ${!trackBlob?'disabled':''}>${icon('play')}${e(t('preview'))}</button><button type="button" class="btn apply-full" id="apply-mix" ${!trackBlob?'disabled':''}>${icon('play')}${e(t('applyMix'))}</button><button class="btn lime" id="export-mix" ${!trackBlob?'disabled':''}>${icon('download')}${e(t('export'))}</button><button class="text-btn reset-btn" id="reset-fx">${e(t('reset'))}</button><p class="fineprint">${e(t('studioFine'))}</p></section></div><p class="demo-note">${icon('info')}${e(t(demo?'demoStudio':'processingNote'))}</p>`;
}
function render() {
  document.documentElement.lang = language;document.body.classList.toggle('studio-open',route==='studio');
  document.querySelectorAll('[data-i18n]').forEach(node=>node.textContent=t(node.dataset.i18n));
  const nav = ['home','search','charts','library','studio'].map(key=>`<button class="${route===key?'active':''}" data-go="${key}" ${route===key?'aria-current="page"':''}>${icon(key)}<span>${e(t(key))}</span></button>`).join('');
  $('desktop-nav').innerHTML=nav; $('mobile-nav').innerHTML=nav;
  $('connection').textContent=t(demo?'demo':'connected'); $('language').textContent=language==='ru'?'EN':'RU';
  $('content').innerHTML=failed?empty('authError','authHint','info'):({home,search:searchScreen,charts:chartsScreen,library:libraryScreen,studio}[route])();
  if(route==='home'&&resumeState&&trackById(resumeState.id))$('content').insertAdjacentHTML('afterbegin',`<button class="resume-card" id="resume-track">${icon('play')}<span><strong>${e(t('resume'))}</strong><small>${e(trackById(resumeState.id).title)} &middot; ${stamp(resumeState.position)}</small></span></button>`);
  if(route==='studio')$('content').querySelector('.studio-controls').insertAdjacentHTML('afterbegin',`<div class="studio-recipes"><h3>${e(t('presets'))}</h3><div class="recipe-grid">${['clean','warm','night','bright'].map(key=>`<button type="button" class="chip" data-recipe="${key}">${e(t(key))}</button>`).join('')}</div><div class="control-label"><label for="treble">${e(t('treble'))}</label><output>${engine.treble} dB</output></div><input id="treble" class="control-range" type="range" min="-6" max="6" step="1" value="${engine.treble}"><button type="button" class="btn secondary" id="compare-fx" aria-pressed="${engine.bypass}">${e(t(engine.bypass?'dry':'compare'))}</button><div class="studio-advanced"><label>${e(t('format'))}<select id="mix-format">${['mp3','wav'].map(f=>`<option value="${f}" ${f===exportFormat?'selected':''}>${f.toUpperCase()}</option>`).join('')}</select></label><section class="effect-rack"><div class="rack-heading"><h3>${e(t('effectRack'))}</h3><span>${studioEffects.length}/8</span></div><p class="fineprint">${e(t('liveNote'))}</p><div class="effect-grid">${['reverb','echo','delay','lofi','normalize','compressor','equalizer','mastering','pro_reverb','highpass','lowpass','reverse','tremolo','distortion','stereo'].map((f,i)=>`<button type="button" class="effect-tile ${studioEffects.includes(f)?'selected':''}" data-effect="${f}" aria-pressed="${studioEffects.includes(f)}" ${studioEffects.length>=8&&!studioEffects.includes(f)?'disabled':''}><span class="effect-glyph">${['~','&#9678;','///','&#9682;','=','&#8779;','&#9783;','&#10022;','&#8734;','&#8599;','&#8600;','&#8630;','&#8779;','&#9889;','&#8646;'][i]}</span><strong>${e(t(f))}</strong><span class="effect-mode">${e(t(liveEffects.has(f)?'live':'renderOnly'))}</span><small>${studioEffects.includes(f)?'&#10003;':''}</small></button>`).join('')}</div><div class="effect-chain">${studioEffects.length?studioEffects.map((f,i)=>`<span>${i+1}. ${e(t(f))}</span>`).join(''):e(t('none'))}</div></section><label>${e(t('pitch'))}<input id="mix-pitch" type="range" min="-12" max="12" step="0.1" value="${studioPitch}"><output id="pitch-value">${studioPitch}</output></label><p class="fineprint">${e(t('pitchNote'))}</p></div><div class="trim-grid">${['trimStart','trimEnd','fade'].map(key=>`<label>${e(t(key))}<input class="studio-number" type="number" min="0" max="${key==='fade'?10:7200}" step="0.1" data-edit="${key}" value="${engine[key]}"></label>`).join('')}</div><button type="button" class="btn secondary" id="save-mix" ${!trackBlob?'disabled':''}>${e(t('saveMix'))}</button></div>`);
  if(route==='studio'){
    $('speed').insertAdjacentHTML('afterend',`<div class="touch-stepper"><button type="button" data-speed-step="-0.05" aria-label="${e(t('speedDown'))}">&minus;</button>${[.75,1,1.25,1.5].map(v=>`<button type="button" data-speed-preset="${v}" aria-pressed="${engine.speed===v}">${v}&times;</button>`).join('')}<button type="button" data-speed-step="0.05" aria-label="${e(t('speedUp'))}">+</button></div>`);
    $('mix-pitch').insertAdjacentHTML('afterend',`<div class="touch-stepper"><button type="button" data-tone-step="-1" aria-label="${e(t('toneDown'))}">&minus;</button>${[-2,0,2].map(v=>`<button type="button" data-tone-preset="${v}" aria-pressed="${studioPitch===v}">${v===0?e(t('original')):v>0?'+'+v:v}</button>`).join('')}<button type="button" data-tone-step="1" aria-label="${e(t('toneUp'))}">+</button></div>`);
    if(studioEffects.some(f=>['reverb','pro_reverb','echo','delay'].includes(f)))document.querySelector('.effect-chain').insertAdjacentHTML('afterend',`<div class="ambience-control"><label for="ambience">${e(t('ambience'))}<output id="ambience-value">${engine.ambience}%</output></label><input id="ambience" type="range" min="0" max="100" step="5" value="${engine.ambience}"></div>`);
    const tempo=document.createElement('section');tempo.className='tempo-panel';tempo.innerHTML=`<div class="tempo-mode"><strong>${e(t('linkTone'))}</strong><button type="button" data-linked="false" aria-pressed="${!engine.linked}">${e(t('independent'))}</button><button type="button" data-linked="true" aria-pressed="${engine.linked}">${e(t('linked'))}</button></div>`;
    const speed=$('speed'),speedLabel=speed.previousElementSibling,steps=speed.nextElementSibling,rangeLabels=steps.nextElementSibling;
    const tone=$('mix-pitch').closest('label'),toneNote=tone.nextElementSibling;
    tempo.append(speedLabel,speed,steps,rangeLabels,tone,toneNote);document.querySelector('.studio-controls').prepend(tempo);syncTempo();
    const grid=document.querySelector('.effect-grid'),extra=document.createElement('details');extra.className='extra-effects';
    extra.innerHTML=`<summary>${e(t('moreEffects'))}</summary><div class="effect-grid"></div>`;
    const everyday=new Set(['reverb','echo','lofi','equalizer','stereo','normalize']);
    for(const tile of [...grid.children])if(!everyday.has(tile.dataset.effect))extra.querySelector('.effect-grid').append(tile);
    extra.open=studioEffects.some(f=>!everyday.has(f));grid.after(extra);
    if(studioEffects.length)document.querySelector('.effect-rack').insertAdjacentHTML('afterend',easyEffectControls()+dspControls());
    const actions=document.createElement('div');actions.className='studio-actions';
    for(const id of ['apply-mix','compare-fx','export-mix','save-mix','preview-mix'])actions.append($(id));
    document.querySelector('.effect-rack').after(actions);
    if(activeRenderJob)actions.insertAdjacentHTML('beforeend',`<button type="button" class="btn secondary" id="cancel-mix">${e(t('cancel'))}</button>`);
  }
  if(route==='studio'&&current?.local&&!failed)$('content').querySelector('.studio-source').insertAdjacentHTML('beforeend',`<button type="button" class="btn secondary" id="save-local-file">${icon('heart')}${e(t('saveToLibrary'))}</button>`);
  $('previous').innerHTML=icon('previous'); $('next').innerHTML=icon('next'); $('repeat').innerHTML=icon('repeat');
  $('open-queue').setAttribute('aria-label',t('queue'));$('volume-icon').innerHTML=icon('volume'); $('expand-studio').innerHTML=icon('studio');
  for (const [id,key] of [['previous','previous'],['next','next'],['repeat','repeat'],['seek','seek'],['volume','volume'],['language','language'],['player-art','nowPlaying'],['open-player','nowPlaying'],['expand-studio','openStudio'],['player-like','favorite']]) $(id).setAttribute('aria-label',t(key));
  if(renderBusy) for(const id of ['preview-mix','export-mix','save-mix','apply-mix']) if($(id))$(id).disabled=true;
  updatePlayer();
  if(route==='charts'&&!chartData&&!chartsLoading&&!chartsError&&!demo)queueMicrotask(loadCharts);
}
function updatePlayer() {
  document.body.classList.toggle('is-playing',!audio.paused);
  $('now-title').textContent=current?.title || t('selectTrack'); $('now-artist').textContent=current?.artist || t('ready');
  $('player-art').className=`mini-art art-${current?color(current):0}`;
  $('player-art').innerHTML=current?.cover?`<img class="cover-image" src="${e(current.cover)}" alt="" referrerpolicy="no-referrer">`:'<span>♪</span>';
  $('player-like').innerHTML=icon('heart'); $('player-like').setAttribute('aria-pressed',String(current?liked(current):false));
  $('play').innerHTML=icon(audio.paused?'play':'pause'); $('play').setAttribute('aria-label',t(audio.paused?'play':'pause'));
  const full=$('full-play');if(full){full.innerHTML=icon(audio.paused?'play':'pause');full.setAttribute('aria-label',t(audio.paused?'play':'pause'));}
}
function navigate(value) {
  if(value!=='search'&&recorder?.state==='recording')recorder.stop();
  route=['home','search','charts','library','studio'].includes(value)?value:'home';
  if (location.hash !== '#'+route) location.hash=route; else render();
}
window.addEventListener('hashchange',()=>{route=location.hash.slice(1);if(!['home','search','charts','library','studio'].includes(route))route='home';render();window.scrollTo(0,0);if(!matchMedia('(prefers-reduced-motion: reduce)').matches)$('content').animate([{opacity:0,transform:'translateY(10px)'},{opacity:1,transform:'translateY(0)'}],{duration:240,easing:'ease-out'});});

async function runSearch(query){
  if(searching)return;searchQuery=query;searching=true;render();
  try{results=demo?demos.filter(s=>(s.title+' '+s.artist).toLowerCase().includes(query.toLowerCase())):(await(await api('search?q='+encodeURIComponent(query))).json()).tracks;}
  catch(error){report(error);results=[];}finally{searching=false;if(route==='search')render();}
}
async function mutate(payload) {
  if (!demo) state=await (await api('library',payload)).json();
  else {
    if(payload.action==='favorite') {
      state.favorites=state.favorites.filter(id=>id!==payload.track);
      if(payload.value)state.favorites.push(payload.track);
    } else if(payload.action==='create')state.playlists.push({id:crypto.randomUUID(),name:payload.name,tracks:[]});
    else if(payload.action==='rename') {const p=state.playlists.find(p=>p.id===payload.playlist);if(p)p.name=payload.name;}
    else if(payload.action==='delete_playlist')state.playlists=state.playlists.filter(p=>p.id!==payload.playlist);
    else if(payload.action==='playlist_remove') {const p=state.playlists.find(p=>p.id===payload.playlist);if(p)p.tracks=p.tracks.filter(id=>id!==payload.track);}
    else if(payload.action==='playlist') {
      const p=state.playlists.find(p=>p.id===payload.playlist);
      const track=trackById(payload.track);
      if(track&&!state.tracks.some(s=>s.id===track.id))state.tracks.push(track);
      if(p&&!p.tracks.includes(payload.track))p.tracks.push(payload.track);
    }
    else if(payload.action==='remove') {state.favorites=state.favorites.filter(id=>id!==payload.track);state.playlists.forEach(p=>p.tracks=p.tracks.filter(id=>id!==payload.track));state.tracks=state.tracks.filter(s=>s.id!==payload.track);}
    try {localStorage.setItem('swidj-demo-library',JSON.stringify(state));}catch{}
  }
  render();
}
async function favorite(track) {
  if(track.local)return saveLocalTrack(track);
  if(!state.tracks.some(s=>s.id===track.id))state.tracks.push(track);
  await mutate({action:'favorite',track:track.id,value:!liked(track)});
}
async function saveLocalTrack(track) {
  if(demo){toast('localSave');return null;}
  if(preparation){toast('preparingOther');return null;}
  const item={track,status:'upload',cancel:false,upload:true};preparation=item;showPreparation();
  try {
    let response;
    if(track.serverTicket)response=await api('studio/save',{ticket:track.serverTicket});
    else{const form=new FormData();form.append('file',track.blob,track.blob.name);response=await fetch('/api/upload',{method:'POST',headers:{'X-Telegram-Init-Data':initData},body:form,credentials:'omit'});}
    if(!response.ok)throw new Error(({413:'fileTooLarge',400:'invalidAudio',507:'storageFull',401:'expired',409:'capacity'})[response.status]||'error');
    const result=await response.json(),oldId=track.id;
    Object.assign(track,result.track,{local:false});delete track.blob;
    localTracks.delete(oldId);extraTracks.set(track.id,track);state=result.library;
    render();toast('saved');return track;
  } finally {if(preparation===item)preparation=null;showPreparation();}
}
function dialog(title, body, actions='') { $('dialog-title').textContent=title;$('dialog-body').innerHTML=body;$('dialog-actions').innerHTML=actions;if(!$('dialog').open)$('dialog').showModal(); }
function newPlaylist() {
  dialog(t('newPlaylist'),`<input id="playlist-name" type="text" maxlength="40" placeholder="${e(t('playlistName'))}" aria-label="${e(t('playlistName'))}" required autocomplete="off">`,`<button class="btn secondary" value="cancel">${e(t('cancel'))}</button><button class="btn" value="create">${e(t('create'))}</button>`);
  $('dialog-form').onsubmit=async event=>{
    if(event.submitter?.value!=='create')return;
    event.preventDefault();const name=$('playlist-name').value.trim();if(!name)return;
    try{await mutate({action:'create',name});$('dialog').close();toast('created');}catch(error){report(error);}
  };
}
function trackMenu(track) {
  $('dialog-form').onsubmit=null;
  dialog(track.title,`<button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="like">${icon('heart')}${e(t(liked(track)?'unsave':'save'))}</button><button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="playlist">${icon('plus')}${e(t('addPlaylist'))}</button><button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="studio">${icon('studio')}${e(t('openStudio'))}</button><button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="send">${icon('send')}${e(t('send'))}</button><button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="remove">${icon('trash')}${e(t('remove'))}</button>`);
  if(playlist&&state.playlists.find(p=>p.id===playlist)?.tracks.includes(track.id))
    $('dialog-body').insertAdjacentHTML('beforeend',`<button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="unlist">${icon('folder')}${e(t('removeFromPlaylist'))}</button>`);
  $('dialog-body').insertAdjacentHTML('afterbegin',`<button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="lyrics">${icon('info')}${e(t('lyrics'))}</button>`);
  $('dialog-body').insertAdjacentHTML('afterbegin',`<button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="queue-next">${icon('next')}${e(t('playNext'))}</button><button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="queue-add">${icon('plus')}${e(t('queueAdd'))}</button>`);
  $('dialog-body').insertAdjacentHTML('afterbegin',`<button type="button" class="dialog-option" data-track="${e(track.id)}" data-action="download">${icon('download')}${e(t('downloadTrack'))}</button>`);
}
function choosePlaylist(track) {
  dialog(t('addPlaylist'),state.playlists.map(p=>`<button type="button" class="dialog-option" data-add-playlist="${e(p.id)}" data-track="${e(track.id)}">${icon('folder')}${e(p.name)}</button>`).join('')+`<button type="button" class="dialog-option" id="new-playlist">${icon('plus')}${e(t('newPlaylist'))}</button>`);
}
function playlistSettings() {
  const selected=state.playlists.find(p=>p.id===playlist);if(!selected)return;
  $('dialog-form').onsubmit=null;
  dialog(selected.name,`<button type="button" class="dialog-option" id="rename-playlist">${icon('studio')}${e(t('rename'))}</button><button type="button" class="dialog-option" id="delete-playlist">${icon('trash')}${e(t('deletePlaylist'))}</button>`);
}
function renamePlaylist() {
  const selected=state.playlists.find(p=>p.id===playlist);if(!selected)return;
  dialog(t('rename'),`<input id="playlist-name" type="text" maxlength="40" required value="${e(selected.name)}" aria-label="${e(t('playlistName'))}">`,`<button class="btn secondary" value="cancel">${e(t('cancel'))}</button><button class="btn" value="rename">${e(t('saveName'))}</button>`);
  $('dialog-form').onsubmit=async event=>{
    if(event.submitter?.value!=='rename')return;event.preventDefault();
    const name=$('playlist-name').value.trim();if(!name)return;
    try{await mutate({action:'rename',playlist:selected.id,name});$('dialog').close();toast('renamed');}catch(error){report(error);}
  };
}
function deletePlaylist() {
  const selected=state.playlists.find(p=>p.id===playlist);if(!selected)return;
  dialog(t('deletePlaylist'),`<p class="dialog-copy">${e(t('playlistDeleteNote'))}</p>`,`<button class="btn secondary" value="cancel">${e(t('cancel'))}</button><button class="btn" value="delete">${e(t('deletePlaylist'))}</button>`);
  $('dialog-form').onsubmit=async event=>{
    if(event.submitter?.value!=='delete')return;event.preventDefault();
    try{await mutate({action:'delete_playlist',playlist:selected.id});playlist=null;filter='playlists';render();$('dialog').close();toast('playlistDeleted');}catch(error){report(error);}
  };
}
function fullPlayer() {
  if(!current)return navigate('library');
  $('dialog-form').onsubmit=null;
  dialog(t('nowPlaying'),`<div class="full-player"><div class="full-player-art">${art(current)}</div><h3>${e(current.title)}</h3><p>${e(current.artist)}</p><input id="full-seek" type="range" min="0" max="1000" value="${$('seek').value}" aria-label="${e(t('seek'))}"><div class="full-times"><span id="full-elapsed">${stamp(audio.currentTime)}</span><span id="full-duration">${stamp(audio.duration)}</span></div><div class="full-controls"><button type="button" class="icon-btn" data-player="previous" aria-label="${e(t('previous'))}">${icon('previous')}</button><button type="button" id="full-play" class="play-main" data-player="play" aria-label="${e(t(audio.paused?'play':'pause'))}">${icon(audio.paused?'play':'pause')}</button><button type="button" class="icon-btn" data-player="next" aria-label="${e(t('next'))}">${icon('next')}</button></div><button type="button" class="btn secondary" data-track="${e(current.id)}" data-action="studio">${icon('studio')}${e(t('openStudio'))}</button></div>`);
  $('dialog-body').querySelector('.full-player>.btn').insertAdjacentHTML('beforebegin',`<button type="button" class="btn secondary" data-track="${e(current.id)}" data-action="lyrics">${e(t('lyrics'))}</button>`);
  $('dialog-body').querySelector('.full-player>.btn').insertAdjacentHTML('beforebegin',`<button type="button" class="btn" data-track="${e(current.id)}" data-action="download">${icon('download')}${e(t('downloadTrack'))}</button>`);
}
async function refreshLibrary() {
  if(demo||failed||refreshing)return;
  refreshing=true;
  try{state=await(await api('library')).json();render();}finally{refreshing=false;}
}
function showPreparation() {
  $('activity').hidden=!preparation;
  if(!preparation)return;
  $('activity-title').textContent=preparation.track.title;
  $('activity-label').textContent=t(preparation.upload?'savingFile':preparation.cancel?'cancelling':preparation.status==='resolving'?'resolving':preparation.status==='queued'?'queued':'preparing');
  $('cancel-prepare').textContent=t('cancel');
  $('cancel-prepare').hidden=Boolean(preparation.upload);
  $('cancel-prepare').disabled=preparation.cancel;
}
async function prepareTrack(track) {
  if(preparation){toast('preparingOther');return null;}
  const item={track,status:'resolving',cancel:false,job:null};preparation=item;showPreparation();
  try {
    let info=await(await api('prepare',{track:track.id})).json();
    if(info.status==='choices') {
      for(const choice of info.tracks)extraTracks.set(choice.id,choice);
      while(extraTracks.size>40)extraTracks.delete(extraTracks.keys().next().value);
      $('dialog-form').onsubmit=null;
      dialog(t('chooseVersion'),info.tracks.length?info.tracks.map(choice=>`<button type="button" class="dialog-option" data-track="${e(choice.id)}" data-action="play">${icon('play')}<span>${e(choice.title)}<small class="version-artist">${e(choice.artist)} · ${stamp(choice.duration)}</small></span></button>`).join(''):`<p class="dialog-copy">${e(t('noResults'))}</p>`);
      return null;
    }
    item.job=info.job;const deadline=Date.now()+1200000;
    while(['queued','downloading','cancelling'].includes(info.status)) {
      if(Date.now()>deadline){if(item.job)api('jobs/'+item.job+'/cancel',{}).catch(()=>{});throw new Error('downloadTimeout');}
      item.status=info.status;showPreparation();
      if(item.cancel&&item.job)await api('jobs/'+item.job+'/cancel',{});
      await new Promise(resolve=>setTimeout(resolve,900));
      info=await(await api('jobs/'+item.job)).json();
    }
    if(info.status==='cancelled'||item.cancel){toast('cancelled');return null;}
    if(info.status!=='ready')throw new Error(['queueTimeout','downloadTimeout'].includes(info.error)?info.error:'prepareFailed');
    Object.assign(track,info.track);
    extraTracks.set(track.id,track);
    return track;
  } finally {if(preparation===item)preparation=null;showPreparation();}
}
async function playTrack(track) {
  if(preparation){toast('preparingOther');return false;}
  if(current?.id===track.id&&trackUrl){
    if(previewUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;engine.setProcessed(false);engine.setBass(engine.bass);engine.setSpeed(engine.speed);}
    await engine.unlock();try{await audio.play();}catch{toast('readyToPlay');}return true;
  }
  document.querySelector('.link-result video')?.pause();document.querySelector('.link-result audio')?.pause();
  const ticket=++loadingTrack;
  await engine.unlock();
  if(!demo&&!track.local){const ready=await prepareTrack(track);if(!ready)return false;}
  if($('dialog').open&&!$('full-play'))$('dialog').close();
  let blob;
  if(track.local)blob=localTracks.get(track.id)?.blob;
  else if(demo) {const response=await fetch(`/demo/${track.demo}.wav`);if(!response.ok)throw new Error('invalidAudio');blob=await response.blob();}
  else blob=await (await api('audio/'+encodeURIComponent(track.id))).blob();
  if(ticket!==loadingTrack)return false;
  audio.pause();engine.setProcessed(false);lastRendered=null;engine.trimStart=0;engine.trimEnd=0;engine.fade=0;if(trackUrl)URL.revokeObjectURL(trackUrl);if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null;}
  trackBlob=blob;trackUrl=URL.createObjectURL(blob);audio.src=trackUrl;current=track;
  engine.setBass(engine.bass);engine.setSpeed(engine.speed);
  try{await audio.play();}catch(error){if(error.name==='NotAllowedError')toast('readyToPlay');else throw error;}
  if(playHistory.at(-1)!==track.id)playHistory.push(track.id);playHistory=playHistory.slice(-100);persistSession();
  sourceDuration=audio.duration;updatePlayer();if(route==='studio')render();if($('dialog').open&&$('full-play'))fullPlayer();return true;
}
async function togglePlay() {
  if(!audio.src) {const track=state.tracks[0];if(track)return playTrack(track);return navigate('search');}
  await engine.unlock();if(audio.paused)await audio.play();else audio.pause();updatePlayer();
}
async function nextTrack(direction=1) {
  if(direction<0&&playHistory.length>1){playHistory.pop();const previous=trackById(playHistory.pop());if(previous)return playTrack(previous);}
  if(direction>0){while(playQueue.length){const queued=trackById(playQueue[0]);if(!queued){playQueue.shift();continue;}if(await playTrack(queued)){playQueue.shift();persistSession();}return;}}

  let tracks=state.tracks;
  const selected=state.playlists.find(p=>p.id===playlist);
  if(route==='library'&&selected)tracks=selected.tracks.map(trackById).filter(Boolean);
  else if(route==='library'&&filter==='favorites')tracks=tracks.filter(liked);
  else if(route==='search'&&results)tracks=results;
  const queue=tracks;if(!queue.length)return;
  const index=queue.findIndex(s=>s.id===current?.id);await playTrack(queue[(index+direction+queue.length)%queue.length]);
}
async function sendTrack(track) {
  if(demo)return toast('demoSend');if(track.local&&!await saveLocalTrack(track))return;
  await api('send',{track:track.id});$('dialog').close();toast('sent');
}
async function downloadTrack(track) {
  if(track.local&&track.serverTicket){showExportDownload({url:location.origin+'/studio-file/'+track.serverTicket,filename:track.blob.name});nativeExportDownload();return;}
  if(!await playTrack(track))return;
  if(!demo&&!track.local&&typeof tg?.downloadFile==='function'&&tg.isVersionAtLeast?.('8.0')!==false) {
    const ticket=await(await api('download',{track:track.id})).json();
    tg.downloadFile({url:ticket.url,file_name:ticket.filename});
    return;
  }
  const url=URL.createObjectURL(trackBlob),a=document.createElement('a');
  const extension=trackBlob.type.includes('wav')||demo?'wav':track.local?(track.blob.name.split('.').pop()||'audio'):'mp3';
  a.href=url;a.download=track.title.replace(/[\\/:*?"<>|]/g,'').slice(0,100)+'.'+extension;
  a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
}
let toneTimer=null,toneRevision=0;
function scheduleTone(){
  clearTimeout(toneTimer);const revision=++toneRevision,track=loadingTrack;
  if(engine.linked||demo||!trackBlob)return;
  const run=async()=>{
    if(revision!==toneRevision||track!==loadingTrack||engine.linked||route!=='studio')return;
    if(renderBusy){toneTimer=setTimeout(run,350);return;}
    toast('tonePending');await renderMix('tone');
  };
  toneTimer=setTimeout(run,550);
}
let activeRenderJob=null,previewStart=0;
async function processMix(preview=false,delivery=false,auditionStart=null) {
  if(demo){if(exportFormat==='mp3'||studioPitch||studioEffects.length)throw new Error('needsTelegram');return engine.render(trackBlob,preview,sourceDuration);}
  const settings={background:true,preview,delivery:delivery?'ticket':'inline',title:(current?.title||'SwiDJ')+' - SwiDJ mix',format:preview?'mp3':exportFormat,start:engine.trimStart,end:engine.trimEnd||0,speed:engine.speed,pitch:studioPitch,bass:engine.bass,treble:engine.treble,effects:[...studioEffects],linked:engine.linked,params:{...engine.params},ambience:engine.ambience,fade:engine.fade};
  if(auditionStart!==null)settings.start=auditionStart;
  let body,headers={'X-Telegram-Init-Data':initData};
  if(current?.serverTicket||!current?.local){
    if(current.serverTicket&&current.local)settings.source_ticket=current.serverTicket;else settings.source_track=String(current.id);
    headers['Content-Type']='application/json';body=JSON.stringify(settings);
  }else{body=new FormData();body.append('settings',JSON.stringify(settings));body.append('file',trackBlob,'source.audio');}
  const response=await fetch('/api/studio',{method:'POST',headers,body,credentials:'omit'});
  if(!response.ok)throw new Error(({413:'studioSize',400:'studioInvalid',410:'linkExpired',401:'expired',429:'rateLimit',504:'studioTimeout'})[response.status]||'error');
  if(response.headers.get('content-type')?.startsWith('audio/'))return response.blob();
  let info=await response.json();
  if(info.job){
    activeRenderJob=info.job;if(route==='studio')render();const deadline=Date.now()+1200000;
    try{
      while(['queued','processing'].includes(info.status)){
        if(Date.now()>deadline){api('studio/jobs/'+activeRenderJob+'/cancel',{}).catch(()=>{});throw new Error('studioTimeout');}
        await new Promise(resolve=>setTimeout(resolve,900));info=await(await api('studio/jobs/'+activeRenderJob)).json();
      }
      if(info.status==='cancelled')throw new Error('cancelled');
      if(info.status!=='ready')throw new Error(copy.en[info.error]?info.error:'error');
      info=info.file;
    }finally{activeRenderJob=null;}
  }
  if(delivery)return info;
  const file=await fetch(info.url,{credentials:'omit'});if(!file.ok)throw new Error('linkExpired');return file.blob();
}

function downloadLabel(file){return /\.mp4$/i.test(file?.filename||'')?'downloadVideo':/\.mp3$/i.test(file?.filename||'')?'downloadAudio':'downloadFile';}
function linkScreen(){return heading('linkTitle','linkNote')+`<section class="link-panel"><input id="link-url" type="url" value="${e(linkUrl)}" placeholder="${e(t('linkPlaceholder'))}" aria-label="${e(t('linkPlaceholder'))}" maxlength="2048"><div class="link-options"><label><input type="radio" name="link-type" value="audio" ${linkType==='audio'?'checked':''}>${e(t('audioMode'))}</label><label><input type="radio" name="link-type" value="video" ${linkType==='video'?'checked':''}>${e(t('videoMode'))}</label></div>${linkType==='video'?`<label class="quality-label">${e(t('quality'))}<select id="link-quality">${[144,240,360,480,720,1080,0].map(q=>`<option value="${q}" ${linkQuality===q?'selected':''}>${q?q+'p':e(t('original'))}</option>`).join('')}</select></label>`:''}<button type="button" class="btn" id="prepare-link" ${linkBusy?'disabled':''}>${e(t(linkBusy?'linkBusy':linkType==='video'?'getVideo':'getAudio'))}</button>${linkBusy?`<div class="media-progress" role="status"><span></span><p>${e(t('mediaPreparing'))}</p></div><button type="button" class="text-btn" id="cancel-link">${e(t('linkCancel'))}</button>`:''}</section>${linkResult?`<section class="link-result"><h2>${e(linkResult.title)}</h2><p>${e(linkResult.artist||'')}</p><button type="button" class="btn primary-media-download" id="download-link">${icon('download')}${e(t(downloadLabel(linkResult)))}</button>${linkResult.kind==='video'?`<video id="link-video" controls playsinline poster="${e(linkResult.poster||'')}" preload="metadata" src="${e(linkResult.url)}"></video>`:`<audio controls preload="metadata" src="${e(linkResult.url)}"></audio>`}<div class="link-result-actions">${linkResult.kind==='video'?`<button type="button" class="btn secondary" id="expand-video">${e(t('expandVideo'))}</button>`:''}${linkResult.kind==='video'&&linkResult.has_audio!==false?`<button type="button" class="btn secondary" id="extract-link-audio">${e(t('extractAudio'))}</button>`:''}${linkResult.kind==='audio'?`<button type="button" class="btn secondary" id="studio-link">${e(t('openMediaStudio'))}</button>`:''}</div><button type="button" class="text-btn" id="new-media-link">${e(t('newLink'))}</button></section>`:''}${linkAudioResult?`<section class="link-result extracted-result"><h2>${e(t('extractAudio'))}</h2><audio controls preload="metadata" src="${e(linkAudioResult.url)}"></audio><div class="link-result-actions"><button type="button" class="btn" id="download-extracted">${icon('download')}${e(t('downloadAudio'))}</button><button type="button" class="btn secondary" id="studio-link">${e(t('openMediaStudio'))}</button></div></section>`:''}`;}
async function importLink(){
  if(demo)return toast('needsTelegram');if(linkBusy||!linkUrl.trim())return;
  try{const host=new URL((linkUrl.match(/https?:\/\/\S+/)||[])[0]).hostname;if(['soundcloud.com','www.soundcloud.com','on.soundcloud.com','open.spotify.com','music.apple.com','music.yandex.ru','music.yandex.com'].includes(host)||host.endsWith('.bandcamp.com'))linkType='audio';}catch{}
  const previousResult=linkResult;document.activeElement?.blur();linkBusy=true;linkController=new AbortController();const timer=setTimeout(()=>linkController.abort(),1230000);render();
  try{
    const response=await fetch('/api/link',{method:'POST',headers:{'X-Telegram-Init-Data':initData,'Content-Type':'application/json'},body:JSON.stringify({url:linkUrl.trim(),mode:linkType,height:linkQuality}),signal:linkController.signal,credentials:'omit'});
    if(!response.ok){let reason;try{reason=(await response.json()).reason;}catch{}throw new Error(copy.en[reason]?reason:({429:'rateLimit',401:'expired',400:'unsupportedLink',504:'studioTimeout'})[response.status]||'linkFailed');}
    const data=await response.json();
    if(data.kind==='search'){searchQuery=data.query;results=(await(await api('search?q='+encodeURIComponent(searchQuery))).json()).tracks;linkMode=false;}
    else {linkResult=data;linkAudioResult=null;}
  }catch(error){if(error.name==='AbortError')toast('cancelled');else report(error);}finally{clearTimeout(timer);linkBusy=false;linkController=null;if(route==='search'){render();if(linkMode&&linkResult!==previousResult)document.querySelector('.link-result')?.scrollIntoView({block:'start',behavior:'smooth'});}}
}
document.addEventListener('play',event=>{if(event.target.closest?.('.link-result')){audio.pause();document.querySelectorAll('.link-result video,.link-result audio').forEach(media=>{if(media!==event.target)media.pause();});updatePlayer();}},true);
function setStudioSpeed(value){engine.setSpeed(Math.max(.5,Math.min(2,value)));if(engine.linked)studioPitch=12*Math.log2(engine.speed);}
function setStudioPitch(value){studioPitch=Math.max(-12,Math.min(12,value));if(engine.linked)engine.setSpeed(2**(studioPitch/12));}
function syncTempo(){if($('speed')){$('speed').value=engine.speed;$('speed-value').textContent=engine.speed.toFixed(2)+'\u00d7';}if($('mix-pitch')){$('mix-pitch').value=studioPitch;$('pitch-value').textContent=Number(studioPitch.toFixed(2));}}
const paramGroups={equalizer:['eq60','eq250','eq1000','eq4000','eq12000'],reverb:['room_s'],pro_reverb:['room_s'],echo:['delay_ms','feedback'],delay:['delay_ms','feedback'],lofi:['lofi_hz'],highpass:['highpass_hz'],lowpass:['lowpass_hz'],compressor:['comp_threshold','comp_ratio','comp_attack','comp_release'],stereo:['stereo_width'],tremolo:['tremolo_rate','tremolo_depth'],distortion:['drive']};
const paramRanges={eq60:[-12,12,1],eq250:[-12,12,1],eq1000:[-12,12,1],eq4000:[-12,12,1],eq12000:[-12,12,1],room_s:[.2,3,.1],delay_ms:[60,1000,10],feedback:[0,.65,.05],lofi_hz:[500,3500,100],highpass_hz:[20,6000,20],lowpass_hz:[100,20000,100],comp_threshold:[-48,-6,1],comp_ratio:[1,12,.5],comp_attack:[1,100,1],comp_release:[20,1000,10],stereo_width:[0,2,.1],tremolo_rate:[.5,12,.5],tremolo_depth:[0,1,.05],drive:[1,8,.5]};
const easyEffectSettings={
  reverb:[{room_s:.4},{room_s:1.1},{room_s:2.2}],pro_reverb:[{room_s:.5},{room_s:1.2},{room_s:2.4}],
  echo:[{delay_ms:180,feedback:.1},{delay_ms:280,feedback:.3},{delay_ms:420,feedback:.5}],
  delay:[{delay_ms:120,feedback:.1},{delay_ms:250,feedback:.25},{delay_ms:500,feedback:.5}],
  lofi:[{lofi_hz:3500},{lofi_hz:2000},{lofi_hz:900}],
  compressor:[{comp_threshold:-18,comp_ratio:2},{comp_threshold:-26,comp_ratio:4},{comp_threshold:-32,comp_ratio:8}],
  equalizer:[{eq60:1,eq250:1,eq1000:0,eq4000:1,eq12000:1},{eq60:3,eq250:1,eq1000:0,eq4000:2,eq12000:2},{eq60:5,eq250:2,eq1000:0,eq4000:3,eq12000:3}],
  highpass:[{highpass_hz:60},{highpass_hz:180},{highpass_hz:600}],lowpass:[{lowpass_hz:12000},{lowpass_hz:6000},{lowpass_hz:2000}],
  stereo:[{stereo_width:1.15},{stereo_width:1.5},{stereo_width:1.9}],
  tremolo:[{tremolo_rate:3,tremolo_depth:.15},{tremolo_rate:5,tremolo_depth:.4},{tremolo_rate:7,tremolo_depth:.75}],
  distortion:[{drive:1.3},{drive:2.5},{drive:5}]
};
function easyEffectControls(){return `<section class="easy-effect-controls"><h3>${e(t('effectStrength'))}</h3>${studioEffects.filter(f=>easyEffectSettings[f]).map(f=>`<div class="easy-effect-row"><strong>${e(t(f))}</strong><div class="touch-stepper">${['gentleFx','balancedFx','strongFx'].map((key,i)=>`<button type="button" data-easy-effect="${f}" data-strength="${i}" aria-pressed="${Object.entries(easyEffectSettings[f][i]).every(([k,v])=>engine.params[k]===v)}">${e(t(key))}</button>`).join('')}</div></div>`).join('')}</section>`;}
function dspControls(){const seen=new Set();return `<details class="dsp-panel"><summary>${e(t('fineTune'))}</summary><button type="button" class="text-btn" id="reset-effect-controls">${e(t('resetEffectControls'))}</button>${studioEffects.map(f=>{const keys=(paramGroups[f]||[]).filter(k=>!seen.has(k));keys.forEach(k=>seen.add(k));return keys.length?`<section><h3>${e(t(f))}</h3>${keys.map(k=>`<label for="param-${k}">${e(t(k))}<output id="value-${k}">${engine.params[k]}</output></label><input id="param-${k}" data-param="${k}" type="range" min="${paramRanges[k][0]}" max="${paramRanges[k][1]}" step="${paramRanges[k][2]}" value="${engine.params[k]}">`).join('')}</section>`:'';}).join('')}</details>`;}
let lyricMatches=[];
async function showLyrics(track){
  if(demo)return toast('needsTelegram');
  dialog(t('lyrics'),`<p>${e(t('lyricsLoading'))}</p>`);
  try{const data=await(await api('lyrics?track='+encodeURIComponent(track.id))).json();lyricMatches=data.matches||[];
    if(!lyricMatches.length)return dialog(t('lyrics'),`<p>${e(t('lyricsEmpty'))}</p>`);
    if(lyricMatches.length===1)return readLyrics(0);
    dialog(t('lyricsChoose'),lyricMatches.map((m,i)=>`<button type="button" class="dialog-option" data-lyric="${i}"><span>${e(m.title)}<small>${e(m.artist)}</small></span></button>`).join(''));
  }catch(error){$('dialog').close();throw error;}
}
function readLyrics(index){const item=lyricMatches[index];if(item)dialog(item.title,`<p class="lyric-artist">${e(item.artist)} / LRCLIB</p><pre class="lyrics-text">${e(item.text)}</pre>`);}
let currentExport=null;
function showExportDownload(file){
  currentExport=file;
  dialog(t('downloadReady'),`<p class="dialog-copy">${e(file.filename)}</p><button type="button" class="btn" id="native-export">${icon('download')}${e(t(downloadLabel(file)))}</button><a class="btn secondary export-link" href="${e(file.url)}" target="_blank" rel="noopener noreferrer" download="${e(file.filename)}">${e(t('openDownload'))}</a><p class="fineprint">${e(t('iphoneSave'))}</p>`);
}
function nativeExportDownload(){
  if(!currentExport)return;
  if(typeof tg?.downloadFile==='function'&&tg.isVersionAtLeast?.('8.0')!==false){try{tg.downloadFile({url:currentExport.url,file_name:currentExport.filename});return;}catch{}}
  const link=document.querySelector('.export-link');if(link)link.click();
}
async function recordVoice(mode='words'){
  if(demo)return toast('voiceDemo');
  if(recorder?.state==='recording'){recorder.stop();return;}
  if(recordPending||recognitionBusy)return;
  if(mode==='music')await engine.unlock();
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined')return toast('voiceDenied');
  recordPending=true;
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    if(route!=='search'){stream.getTracks().forEach(t=>t.stop());return;}
    recordStream=stream;
    const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(x=>MediaRecorder.isTypeSupported(x));
    recorder=new MediaRecorder(stream,mime?{mimeType:mime}:{});
    const activeRecorder=recorder,forMusic=mode==='music';const panel=forMusic?'.recognition-panel':'.voice-panel';const chunks=[];let bytes=0;
    if(forMusic){recognitionMatches=null;recognitionTrack=null;audio.pause();document.querySelector('.recognition-panel audio')?.pause();}
    recorder.ondataavailable=event=>{chunks.push(event.data);bytes+=event.data.size;if(bytes>8*1024**2&&recorder.state==='recording')recorder.stop();};
    recorder.onstop=()=>{clearTimeout(recordTimer);stream.getTracks().forEach(t=>t.stop());recordStream=null;const blob=new Blob(chunks,{type:activeRecorder.mimeType});if(forMusic)setRecognition(blob);else{voiceBlob=blob;if(voiceUrl)URL.revokeObjectURL(voiceUrl);voiceUrl=URL.createObjectURL(voiceBlob);}if(route==='search'){render();document.querySelector(panel).open=true;if(forMusic&&document.visibilityState==='visible')identifyMusic();}};
    recorder.start(500);recordTimer=setTimeout(()=>{if(recorder?.state==='recording')recorder.stop();},28000);render();document.querySelector(panel).open=true;
  }catch{recordStream?.getTracks().forEach(t=>t.stop());recordStream=null;toast('voiceDenied');}finally{recordPending=false;}
}
async function transcribeVoice(){
  if(demo)return toast('voiceDemo');if(voiceBusy||!voiceBlob)return;
  if(voiceBlob.size>8*1024**2)return toast('voiceLimit');
  voiceBusy=true;render();document.querySelector('.voice-panel').open=true;
  try{
    const form=new FormData();form.append('file',voiceBlob,'voice.audio');
    const response=await fetch('/api/voice',{method:'POST',headers:{'X-Telegram-Init-Data':initData},body:form,credentials:'omit'});
    if(!response.ok)throw new Error(({400:'voiceLimit',413:'voiceLimit',401:'expired',429:'rateLimit',504:'studioTimeout'})[response.status]||'error');
    const data=await response.json();if(!data.text?.trim())return toast('voiceEmpty');
    searchQuery=data.text.slice(0,120);
  }finally{voiceBusy=false;if(route==='search'){render();$('search-input').focus();}}
}
async function renderMix(preview,keepPosition=false) {
  if(renderBusy)return;
  clearTimeout(toneTimer);toneRevision++;
  if(!trackBlob)return toast('chooseFirst');
  engine.setBypass(false);
  const ticket=loadingTrack,bass=engine.bass,speed=engine.speed,treble=engine.treble,bypass=engine.bypass,format=exportFormat,pitch=studioPitch,effect=JSON.stringify(studioEffects),signature=studioSignature();
  renderBusy=true;
  const applying=preview==='apply',tonePreview=preview==='tone';
  const end=engine.trimEnd||sourceDuration;
  const auditionStart=tonePreview?Math.max(engine.trimStart,Math.min(audio.currentTime,Number.isFinite(end)?Math.max(engine.trimStart,end-1):engine.trimStart)):null;
  const resumeAt=keepPosition?audio.currentTime/(engine.processed?1:engine.speed):0;
  const button=$(applying?'apply-mix':preview?'preview-mix':'export-mix');button.disabled=true;button.textContent=t('rendering');
  try {
    const nativeExport=!preview&&!demo;
    const remotePlayback=(applying||tonePreview)&&!demo;
    const blob=await processMix(applying?false:Boolean(preview),nativeExport||remotePlayback,auditionStart);
    if(signature!==studioSignature()||ticket!==loadingTrack||bass!==engine.bass||speed!==engine.speed||treble!==engine.treble||bypass!==engine.bypass||format!==exportFormat||pitch!==studioPitch||effect!==JSON.stringify(studioEffects))return;
    const streamFile=remotePlayback&&typeof blob.url==='string';
    if(preview) {
      if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=streamFile?blob.url:URL.createObjectURL(blob);
      if(!bypass&&!tonePreview)lastRendered=streamFile?{url:blob.url,key:studioSignature()}:{blob,key:studioSignature()};

      previewStart=tonePreview?auditionStart:engine.trimStart;
      audio.src=previewUrl;audio.playbackRate=1;
      // Rendered audio already includes settings: do not apply the live chain twice.
      engine.setProcessed(true);
      if(keepPosition)audio.currentTime=Math.max(0,resumeAt);
      await audio.play();toast(applying?'mixApplied':'previewReady');
    } else if(nativeExport){
      showExportDownload(blob);
      if(typeof tg?.downloadFile==='function'&&tg.isVersionAtLeast?.('8.0')!==false)nativeExportDownload();
    } else {
      const url=URL.createObjectURL(blob),a=document.createElement('a');
      a.href=url;a.download=(current?.title || 'SwiDJ').replace(/[\\/:*?"<>|]/g,'').slice(0,80)+' - SwiDJ mix.'+format;
      a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);toast('exportReady');
    }
  } finally {renderBusy=false;if(route==='studio')render();}
}

document.addEventListener('click',async event=>{
  const button=event.target.closest('button,a,label');if(!button)return;
  try {
    if(button.dataset.mediaMode){linkMode=true;linkType=button.dataset.mediaMode;return navigate('search');}
    if(button.id==='new-media-link'){document.querySelector('#link-video')?.pause();document.querySelector('.link-result audio')?.pause();linkResult=null;linkAudioResult=null;linkUrl='';render();$('link-url')?.focus();return;}
    if(button.id==='expand-video'){const video=$('link-video');if(video?.requestFullscreen)await video.requestFullscreen();else if(video?.webkitEnterFullscreen)video.webkitEnterFullscreen();return;}
    if(button.id==='download-extracted'&&linkAudioResult){showExportDownload(linkAudioResult);nativeExportDownload();return;}
    if(button.id==='record-music')return await recordVoice('music');
    if(button.id==='recognize-music')return await identifyMusic();
    if(button.dataset.recognitionMatch!==undefined){const match=recognitionMatches?.[Number(button.dataset.recognitionMatch)];if(match)await runSearch(match.query);return;}
    if(button.id==='refresh-charts')return await loadCharts();
    if(button.dataset.chartPlay!==undefined)return await playChart(button.dataset.chartPlay);
    if(button.id==='cancel-mix'&&activeRenderJob){await api('studio/jobs/'+activeRenderJob+'/cancel',{});return;}
    if(button.dataset.easyEffect){const values=easyEffectSettings[button.dataset.easyEffect]?.[Number(button.dataset.strength)];if(values){const playing=!audio.paused;invalidateMix();engine.setBypass(false);engine.setParams({...values});render();if(playing)await audio.play();}return;}
    if(button.id==='reset-effect-controls'){invalidateMix();engine.setParams({...dspDefaults});return render();}
    if(button.dataset.linked!==undefined){const playing=!audio.paused;invalidateMix();engine.setLinked(button.dataset.linked==='true');if(engine.linked)studioPitch=12*Math.log2(engine.speed);render();if(playing)await audio.play();if(!engine.linked&&studioPitch!==0)scheduleTone();return;}
    if(button.dataset.openLinks!==undefined){linkMode=true;return navigate('search');}
    if(button.dataset.searchTab){linkMode=button.dataset.searchTab==='links';return render();}
    if(button.id==='prepare-link')return await importLink();
    if(button.id==='cancel-link'){linkController?.abort();api('link/cancel',{}).catch(()=>{});return;}
    if(button.id==='extract-link-audio'&&linkResult){button.disabled=true;button.textContent=t('rendering');try{document.querySelector('#link-video')?.pause();linkAudioResult=await(await api('link/audio',{ticket:new URL(linkResult.url).pathname.split('/').pop()})).json();}finally{if(route==='search'){render();if(linkAudioResult)document.querySelector('.extracted-result')?.scrollIntoView({block:'start',behavior:'smooth'});}}return;}
    if(button.id==='download-link'&&linkResult){showExportDownload(linkResult);nativeExportDownload();return;}
    if(button.id==='studio-link'&&linkResult){const source=linkAudioResult||linkResult;document.querySelector('#link-video')?.pause();document.querySelector('.extracted-result audio')?.pause();const response=await fetch(source.url,{credentials:'omit'});if(!response.ok)throw new Error('linkExpired');const blob=await response.blob();const track={id:'local:'+crypto.randomUUID(),title:source.title,artist:source.artist||'',kind:'upload',playable:true,local:true,serverTicket:new URL(source.url).pathname.split('/').pop(),blob:new File([blob],source.filename,{type:blob.type})};localTracks.set(track.id,track);await playTrack(track);return navigate('studio');}
    if(button.dataset.speedPreset!==undefined||button.dataset.speedStep!==undefined){const playing=!audio.paused;invalidateMix();engine.setBypass(false);const value=button.dataset.speedPreset!==undefined?Number(button.dataset.speedPreset):engine.speed+Number(button.dataset.speedStep);setStudioSpeed(Math.round(value*100)/100);render();if(playing)await audio.play();return;}
    if(button.dataset.tonePreset!==undefined||button.dataset.toneStep!==undefined){const playing=!audio.paused;invalidateMix();engine.setBypass(false);setStudioPitch(button.dataset.tonePreset!==undefined?Number(button.dataset.tonePreset):studioPitch+Number(button.dataset.toneStep));render();if(engine.linked&&playing)await audio.play();scheduleTone();return;}
    if(button.matches('.export-link')&&typeof tg?.openLink==='function'){event.preventDefault();tg.openLink(button.href);return;}
    if(button.dataset.lyric!==undefined)return readLyrics(Number(button.dataset.lyric));
    if(button.id==='native-export')return nativeExportDownload();
    if(button.dataset.effect){const playing=!audio.paused;invalidateMix();engine.setBypass(false);const value=button.dataset.effect;if(studioEffects.includes(value))studioEffects=studioEffects.filter(x=>x!==value);else if(studioEffects.length<8)studioEffects.push(value);engine.setEffects(studioEffects);render();await engine.unlock();if(playing)await audio.play();return;}
    if(button.id==='apply-mix')return await renderMix('apply');
    if(button.id==='record-voice')return await recordVoice();
    if(button.id==='transcribe-voice')return await transcribeVoice();
    if(button.id==='open-queue')return queueDialog();
    if(button.id==='clear-queue'){playQueue=[];persistSession();return queueDialog();}
    for(const [key,delta] of [['qUp',-1],['qDown',1],['qRemove',0]])if(button.dataset[key]!==undefined){const index=Number(button.dataset[key]);if(delta){const next=index+delta;if(next>=0&&next<playQueue.length)[playQueue[index],playQueue[next]]=[playQueue[next],playQueue[index]];}else playQueue.splice(index,1);persistSession();return queueDialog();}
    if(button.id==='resume-track'){const saved={...resumeState};const track=trackById(saved.id);if(track&&await playTrack(track))audio.currentTime=Math.min(Number(saved.position)||0,Math.max(0,audio.duration-1));return;}
    if(button.dataset.recipe){invalidateMix();if(previewUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;}const values={clean:[0,0,1],warm:[3,-2,1],night:[6,1,.9],bright:[0,4,1] }[button.dataset.recipe];engine.setBypass(false);engine.setBass(values[0]);engine.setTreble(values[1]);engine.setSpeed(values[2]);return render();}
    if(button.id==='compare-fx'){
      const wasPlaying=!audio.paused,pos=audio.currentTime;
      if(previewUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;engine.setProcessed(false);engine.setBypass(true);try{audio.currentTime=pos+engine.trimStart;}catch{}if(wasPlaying)await audio.play();}
      else if(lastRendered?.key===studioSignature()){engine.setBypass(false);previewUrl=lastRendered.url||URL.createObjectURL(lastRendered.blob);audio.src=previewUrl;audio.playbackRate=1;engine.setProcessed(true);await audio.play();}
      else engine.setBypass(!engine.bypass);
      return render();
    }
    if(button.id==='save-mix'){
      if(renderBusy||!trackBlob)return;renderBusy=true;
      try{
        $('save-mix').disabled=true;$('save-mix').textContent=t('rendering');
        if(!demo){const file=await processMix(false,true);const result=await(await api('studio/save',{ticket:new URL(file.url).pathname.split('/').pop()})).json();state=result.library;extraTracks.set(result.track.id,result.track);studioPitch=0;studioEffects=[];engine.setEffects([]);engine.setLinked(false);engine.setParams({...dspDefaults});engine.setBass(0);engine.setTreble(0);engine.setSpeed(1);await playTrack(result.track);toast('saved');}
        else{const blob=await processMix(false);const track={id:'local:'+crypto.randomUUID(),title:current.title+' - SwiDJ mix',artist:'SwiDJ Studio',kind:'upload',playable:true,local:true,blob:new File([blob],'SwiDJ mix.wav',{type:blob.type})};localTracks.set(track.id,track);engine.setBass(0);engine.setTreble(0);engine.setSpeed(1);await playTrack(track);toast('mixSaved');}
      }finally{renderBusy=false;render();}return;
    }
    if(button.dataset.go)return navigate(button.dataset.go);
    if(button.dataset.filter){filter=button.dataset.filter;playlist=null;return render();}
    if(button.dataset.playlist){playlist=button.dataset.playlist;return render();}
    if(button.id==='back-playlists'){playlist=null;filter='playlists';return render();}
    if(button.id==='new-playlist')return newPlaylist();
    if(button.id==='save-local-file'&&current?.local)return await saveLocalTrack(current);
    if(button.id==='cancel-prepare'&&preparation){preparation.cancel=true;showPreparation();return;}
    if(button.id==='playlist-settings')return playlistSettings();
    if(button.id==='rename-playlist')return renamePlaylist();
    if(button.id==='delete-playlist')return deletePlaylist();
    if(button.id==='refresh-library'){await refreshLibrary();return toast('refreshed');}
    if(button.dataset.player==='play')return await togglePlay();
    if(button.dataset.player==='next')return await nextTrack();
    if(button.dataset.player==='previous')return await nextTrack(-1);
    if(button.dataset.addPlaylist){const track=trackById(button.dataset.track);if(!track)return;if(track.local&&!await saveLocalTrack(track))return;await mutate({action:'playlist',track:track.id,playlist:button.dataset.addPlaylist});$('dialog').close();return toast('saved');}
    if(button.dataset.action){
      const track=trackById(button.dataset.track);if(!track)return;
      const action=button.dataset.action;
      if(action==='queue-next'||action==='queue-add'){if(playQueue.length>=100)return toast('capacity');extraTracks.set(track.id,track);if(action==='queue-next')playQueue.unshift(track.id);else playQueue.push(track.id);persistSession();$('dialog').close();return toast('queueAdded');}
      if(action==='play')return await playTrack(track);
      if(action==='lyrics')return await showLyrics(track);
      if(action==='download'){$('dialog').close();return await downloadTrack(track);}
      if(action==='like'){$('dialog').close();return await favorite(track);}
      if(action==='menu')return trackMenu(track);
      if(action==='playlist')return choosePlaylist(track);
      if(action==='unlist'){await mutate({action:'playlist_remove',playlist,track:track.id});$('dialog').close();return;}
      if(action==='send')return await sendTrack(track);
      if(action==='studio'){$('dialog').close();if(await playTrack(track))navigate('studio');return;}
      if(action==='remove'){
        dialog(t('remove'),`<p class="dialog-copy">${e(t(track.app_upload?'removeUploadQuestion':'removeQuestion'))}</p>`,`<button class="btn secondary" value="cancel">${e(t('cancel'))}</button><button class="btn" value="remove">${e(t('remove'))}</button>`);
        $('dialog-form').onsubmit=async event=>{if(event.submitter?.value!=='remove')return;event.preventDefault();try{await mutate({action:'remove',track:track.id,delete_file:track.app_upload===true});$('dialog').close();toast('removed');}catch(error){report(error);}};return;
      }
    }
    if(button.dataset.bass!==undefined){invalidateMix();engine.setBypass(false);if(previewUrl&&trackUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;}engine.setBass(Number(button.dataset.bass));engine.setSpeed(engine.speed);return render();}
    if(button.id==='reset-fx'){clearTimeout(toneTimer);toneRevision++;invalidateMix();studioPitch=0;studioEffects=[];engine.setEffects([]);engine.setLinked(false);engine.setParams({...dspDefaults});engine.setProcessed(false);engine.trimStart=0;engine.trimEnd=0;engine.fade=0;engine.setBass(0);engine.setTreble(0);engine.setBypass(false);engine.setSpeed(1);if(trackUrl)audio.src=trackUrl;return render();}
    if(button.id==='preview-mix')return await renderMix(true);
    if(button.id==='export-mix')return await renderMix(false);
    if(button.id==='play')return await togglePlay();
    if(button.id==='next')return await nextTrack();
    if(button.id==='previous')return await nextTrack(-1);
    if(button.id==='repeat'){audio.loop=!audio.loop;button.setAttribute('aria-pressed',String(audio.loop));return;}
    if(button.id==='player-like'&&current)return await favorite(current);
    if(['player-art','open-player'].includes(button.id))return fullPlayer();
    if(button.id==='expand-studio')return navigate('studio');
    if(button.id==='language'){
      language=language==='ru'?'en':'ru';try{localStorage.setItem('swidj-language',language);}catch{}
      if(!demo&&!failed)await mutate({action:'language',language});render();
    }
  } catch(error){report(error);}
});
document.addEventListener('submit',async event=>{
  if(event.target.id!=='search-form')return;
  event.preventDefault();if(searching)return;const query=$('search-input').value.trim();if(query.length<2)return;
  await runSearch(query);
});
document.addEventListener('input',event=>{
  const node=event.target,wasPlaying=!audio.paused;
  if(node.matches('[data-edit],#speed,#treble,#mix-pitch')){invalidateMix();engine.setBypass(false);}
  if(node.id==='mix-pitch'){clearTimeout(toneTimer);toneRevision++;setStudioPitch(Number(node.value));syncTempo();if(engine.linked&&wasPlaying)audio.play().catch(report);}
  if(node.dataset.edit){engine[node.dataset.edit]=Math.max(0,Math.min(node.dataset.edit==='fade'?10:7200,Number(node.value)||0));}
  if(node.dataset.param){const playing=!audio.paused;invalidateMix();engine.setBypass(false);engine.setParams({[node.dataset.param]:Number(node.value)});$('value-'+node.dataset.param).textContent=node.value;if(playing)audio.play().catch(report);}
  if(node.id==='chart-filter'){chartFilter=node.value;if($('chart-tracks'))$('chart-tracks').innerHTML=chartRows();}
  if(node.id==='link-url')linkUrl=node.value;
  if(node.id==='ambience'){const playing=!audio.paused;invalidateMix();engine.setBypass(false);if(playing)audio.play().catch(report);engine.setAmbience(Number(node.value));$('ambience-value').textContent=engine.ambience+'%';}
  if(node.id==='search-input')searchQuery=node.value;
  if(node.id==='speed'){
    if(previewUrl&&trackUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;engine.setProcessed(false);engine.setBass(engine.bass);}
    setStudioSpeed(Number(node.value));syncTempo();if(wasPlaying)audio.play().catch(report);
  }
  if(node.id==='treble'){if(previewUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;engine.setSpeed(engine.speed);}engine.setTreble(Number(node.value));node.previousElementSibling.querySelector('output').textContent=engine.treble+' dB';}
  if(node.id==='volume')audio.volume=Number(node.value);
  if(['seek','full-seek'].includes(node.id)&&Number.isFinite(audio.duration))audio.currentTime=audio.duration*Number(node.value)/1000;
});
document.addEventListener('change',async event=>{
  if(event.target.id==='chart-country'){chartCountry=event.target.value;chartFilter='';try{localStorage.setItem('swidj-chart-country',chartCountry);}catch{}await loadCharts();return;}
  if(event.target.id==='mix-pitch'||(event.target.id==='speed'&&studioPitch!==0)){scheduleTone();return;}
  if(event.target.name==='link-type'){linkType=event.target.value;return render();}
  if(event.target.id==='link-quality'){linkQuality=Number(event.target.value);return;}
  if(event.target.id==='mix-format'){exportFormat=event.target.value;return;}
  if(event.target.id==='recognition-file'){const file=event.target.files[0];if(!file)return;if(file.size>32*1024**2)return toast('recognitionLimit');setRecognition(file);render();document.querySelector('.recognition-panel').open=true;return;}
  if(event.target.id==='voice-file'){const file=event.target.files[0];if(!file)return;if(file.size>8*1024**2)return toast('voiceLimit');voiceBlob=file;if(voiceUrl)URL.revokeObjectURL(voiceUrl);voiceUrl=URL.createObjectURL(file);render();document.querySelector('.voice-panel').open=true;return;}
  if(event.target.id!=='local-file')return;
  const file=event.target.files[0];if(!file)return;if(file.size>256*1024**2)return toast('fileTooLarge');
  try {
    const track={id:'local:'+crypto.randomUUID(),title:file.name.replace(/\.[^.]+$/,''),artist:t('uploads'),kind:'upload',playable:true,local:true,blob:file};
    localTracks.set(track.id,track);await playTrack(track);render();
  }catch{toast('invalidAudio');}
});
audio.addEventListener('loadedmetadata',()=>{if(!previewUrl&&Number.isFinite(audio.duration))sourceDuration=audio.duration;});
audio.addEventListener('timeupdate',()=>{if(Date.now()-lastPositionSave>3000&&!previewUrl){lastPositionSave=Date.now();persistSession();}$('elapsed').textContent=stamp(audio.currentTime);$('duration').textContent=stamp(audio.duration);$('seek').value=Number.isFinite(audio.duration)?String(audio.currentTime/audio.duration*1000):'0';if($('full-seek')){$('full-seek').value=$('seek').value;$('full-elapsed').textContent=stamp(audio.currentTime);$('full-duration').textContent=stamp(audio.duration);}});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refreshLibrary().catch(report);});
audio.addEventListener('play',updatePlayer);audio.addEventListener('pause',updatePlayer);
audio.addEventListener('error',()=>toast('invalidAudio'));
document.addEventListener('error',event=>{if(event.target.matches?.('.cover-image'))event.target.remove();},true);
audio.addEventListener('ended',()=>{if(previewUrl){audio.src=trackUrl;URL.revokeObjectURL(previewUrl);previewUrl=null;engine.setProcessed(false);engine.setBass(engine.bass);engine.setSpeed(engine.speed);updatePlayer();}else if(!audio.loop)nextTrack().catch(report);});
window.addEventListener('keydown',event=>{if(event.code==='Space'&&!['INPUT','TEXTAREA','BUTTON'].includes(document.activeElement?.tagName)&&!$('dialog').open){event.preventDefault();togglePlay().catch(report);}});
window.addEventListener('pagehide',()=>{clearTimeout(recordTimer);if(recorder?.state==='recording')recorder.stop();recordStream?.getTracks().forEach(t=>t.stop());persistSession();if(trackUrl)URL.revokeObjectURL(trackUrl);if(previewUrl)URL.revokeObjectURL(previewUrl);});

async function start() {
  if(tg){tg.ready();tg.expand();tg.setHeaderColor?.('#101116');tg.setBackgroundColor?.('#101116');}
  route=['home','search','charts','library','studio'].includes(location.hash.slice(1))?location.hash.slice(1):'home';
  $('content').innerHTML=`<div class="loading">${e(t('loading'))}</div>`;
  if(demo) {
    // Only admit expected demo IDs; malformed local storage cannot become a media URL.
    const saved=demoState&&Array.isArray(demoState.tracks)?demoState:null;
    state={tracks:saved?demos.filter(s=>saved.tracks.some(x=>x.id===s.id)):demos,favorites:saved?.favorites?.filter(id=>demos.some(s=>s.id===id)) || ['demo:0','demo:2'],playlists:Array.isArray(saved?.playlists)?saved.playlists.filter(p=>typeof p.name==='string'&&Array.isArray(p.tracks)).slice(0,20):[{id:'evening',name:language==='ru'?'После заката':'After hours',tracks:['demo:0','demo:3']}],bot:''};
  } else {
    try {state=await (await api('library')).json();language=state.language==='en'?'en':'ru';$('avatar').textContent=(tg?.initDataUnsafe?.user?.first_name || 'S').slice(0,1);}
    catch(error){failed=true;report(error);}
  }
  playQueue=playQueue.filter(id=>trackById(id));
  render();
}
start().catch(report);

document.addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.id==='link-url'){event.preventDefault();importLink().catch(report);}});
