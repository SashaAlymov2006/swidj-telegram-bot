"""Concrete user-facing feature inventory, shared by the welcome guide."""
WELCOME={
 'ru':('🎧 <b>SwiDJ</b>\n\n'
       '🔎 Поиск по названию, словам и голосу\n'
       '🔗 Скачивание музыки и видео по ссылкам\n'
       '⭐ Избранное, плейлисты и свои файлы\n'
       '🎛 Тон, скорость, эффекты и экспорт аудио\n'
       '🎚 Две DJ-деки и запись сетов\n'
       '🎬 Создание видео под музыку\n'
       '📄 Тексты песен с подсветкой строк'),
 'en':('🎧 <b>SwiDJ</b>\n\n'
       '🔎 Find songs by title, lyrics and voice\n'
       '🔗 Download music and video from links\n'
       '⭐ Favourites, playlists and your own files\n'
       '🎛 Pitch, speed, effects and audio export\n'
       '🎚 Two DJ decks and set recording\n'
       '🎬 Music-video creation\n'
       '📄 Lyrics with timed highlighting')
}

TOPICS={
 'search':('🔎 Поиск и распознавание','🔎 Search & recognition',
   '• По названию песни и исполнителю\n• По словам песни и голосовому сообщению\n• Опечатки, другая раскладка, приблизительное звучание иностранных слов\n• Распознавание музыкальной записи\n• Поиск по напетой мелодии (beta)\n• Чарты по странам\n• Страницы исполнителей\n• Альбомы, синглы, EP и ремиксы\n• Варианты записи из разных источников\n• Обложки и сведения о треке\n• Переход к оригинальному источнику',
   '• Song title and artist search\n• Lyrics and voice-message search\n• Typos, keyboard-layout mistakes and approximate foreign-word spellings\n• Music-recording recognition\n• Humming search (beta)\n• Charts by country\n• Artist pages\n• Albums, singles, EPs and remixes\n• Recording choices from different sources\n• Cover artwork and track details\n• Original-source links'),
 'links':('🔗 Скачивание по ссылкам','🔗 Link downloads',
   'YouTube · SoundCloud · Spotify\nApple Music · Яндекс Музыка\nTikTok · Instagram',
   'YouTube · SoundCloud · Spotify\nApple Music · Yandex Music\nTikTok · Instagram'),
 'library':('⭐ Коллекция и плеер','⭐ Library & player',
   '• Сохранение найденной музыки и своих аудиофайлов\n• Избранное и плейлисты\n• Создание и переименование плейлистов\n• Добавление, перемещение и удаление треков\n• Общая коллекция бота и Mini App\n• Плеер, перемотка и громкость\n• Предыдущий / следующий трек и повтор\n• Очередь воспроизведения: добавление, порядок, удаление\n• Продолжение прослушивания\n• Перенос трека в аудио-, DJ- или видеостудию',
   '• Save discovered music and your own audio files\n• Favourites and playlists\n• Create and rename playlists\n• Add, move and remove tracks\n• Shared bot and Mini App collection\n• Player, seeking and volume\n• Previous/next track and repeat\n• Playback queue: add, reorder and remove\n• Resume listening\n• Take a track into the audio, DJ or video studio'),
 'studio':('🎛 Аудиостудия','🎛 Audio studio',
   '• Тон и скорость: вместе или независимо\n• Бас и высокие частоты\n• Пятиполосный эквалайзер, High-pass / Low-pass\n• Reverb / Pro Reverb, Echo / Delay, Lo-fi\n• Компрессор, Distortion, Stereo, Tremolo\n• Нормализация громкости и мастеринг\n• Reverse, лупы, обрезка, плавное начало и конец\n• Одновременная работа нескольких эффектов\n• Настройка параметров эффектов\n• Предпрослушивание и сравнение с оригиналом\n• Сохранение своих звуковых пресетов\n• MP3 / WAV, короткие фрагменты и рингтоны\n• Скачивание и отправка результата в чат',
   '• Pitch and speed: linked or independent\n• Bass and treble\n• Five-band EQ, high-pass / low-pass filters\n• Reverb / Pro Reverb, echo / delay, lo-fi\n• Compressor, distortion, stereo, tremolo\n• Loudness normalisation and mastering\n• Reverse, loops, trimming, fade-in and fade-out\n• Combine multiple effects\n• Adjust effect parameters\n• Preview and compare with the original\n• Save your own sound presets\n• MP3 / WAV, short clips and ringtones\n• Download or send the result to chat'),
 'dj':('🎚 DJ-комната','🎚 DJ room',
   '• Две деки с разными треками\n• Волновая форма и перемотка\n• Анализ BPM и сетка ритма\n• Tap Tempo, ручной BPM, ×2 / ½ BPM\n• Отметка первого удара и совмещение ударов\n• Синхронизация темпа дек\n• Тон, скорость, громкость, бас и высокие\n• Cue-точки, петли по тактам и Beat Roll\n• Кроссфейдер, фильтр, Bass Cut, Echo Out\n• Одновременный запуск / пауза дек\n• Сброс деки и эффектов\n• Сохранение, открытие и удаление проектов\n• Запись сета, экспорт MP3 и сохранение в «Мою музыку»\n\nMini App → Студия → DJ',
   '• Two decks with separate tracks\n• Waveforms and seeking\n• BPM analysis and beat grid\n• Tap Tempo, manual BPM, double / half BPM\n• Set the first beat and align beats\n• Match deck tempos\n• Pitch, speed, volume, bass and treble\n• Cue points, bar loops and Beat Roll\n• Crossfader, filter, Bass Cut, Echo Out\n• Start / pause both decks\n• Reset decks and effects\n• Save, open and delete projects\n• Record a set, export MP3 and save to your music\n\nMini App → Studio → DJ'),
 'video':('🎬 Видеостудия','🎬 Video studio',
   '• Музыка из коллекции, своего файла или готового микса\n• 18 готовых оформлений; свои настройки\n• Фон: цвет, картинка или видео\n• Логотип, круг, треугольник, квадрат, шестиугольник, звезда или без фигуры\n• Кольцо, столбики, волны, зеркальный и двойной спектр, рябь\n• Звёзды, искры и снег\n• Пульсация: бас, бит, дыхание, двойной удар\n• Вращение, плавание, орбита и покачивание\n• Цвета, свечение, размытие и виньетка\n• Размер, положение, кадрирование и интенсивность анимации\n• Заголовок, подпись и текст песни\n• Предпросмотр, отмена и возврат правок\n• MP4: 720p / 1080p, 30 / 60 fps\n• Горизонтальный, вертикальный и квадратный кадр\n\nMini App → Студия → Видео',
   '• Music from your library, own file or finished mix\n• 18 ready-made styles and custom settings\n• Background: colour, image or video\n• Logo, circle, triangle, square, hexagon, star or no shape\n• Ring, bars, waves, mirrored/dual spectrum and ripple\n• Stars, sparks and snow\n• Bass, beat, breathing and double-beat pulses\n• Rotation, floating, orbit and sway\n• Colours, glow, blur and vignette\n• Size, position, crop and animation intensity\n• Title, subtitle and lyrics\n• Preview, undo and redo\n• MP4: 720p / 1080p, 30 / 60 fps\n• Landscape, portrait and square\n\nMini App → Studio → Video'),
 'lyrics':('📄 Тексты песен','📄 Lyrics',
   '• Поиск текста найденной песни\n• Чтение прямо в боте и Mini App\n• Открытие и скрытие текста в плеере\n• Обычный текст и подсветка по времени\n• Переход к источнику слов\n• Текст в музыкальном видео\n• Настройка положения, размера, цвета и временного смещения\n• Подсветка, появление и пульсация строк\n• Текст с подложкой или без неё',
   '• Look up a discovered song’s lyrics\n• Read inside the bot and Mini App\n• Show or hide lyrics in the player\n• Plain text and timed highlighting\n• Open the lyrics source\n• Add lyrics to music videos\n• Adjust position, size, colour and time offset\n• Highlight, fade and pulse styles\n• Text with or without a backdrop'),
 'comfort':('⚙ Удобство и управление','⚙ Navigation & controls',
   '• Русский / English, сохранение языка\n• История поиска\n• Сохранение запроса, раздела и прокрутки Mini App\n• Возврат из студии к прежнему поиску\n• Повторение устаревшего поиска одной кнопкой\n• Выбор другой версии записи\n• Общие коллекции и язык в боте и приложении\n• Очередь задач, ожидание, повтор и отмена\n• Повторная выдача сохранённых файлов\n• Меню, помощь и панель владельца для администратора',
   '• Russian / English with saved language\n• Search history\n• Saved query, section and Mini App scroll position\n• Return from the studio to your previous search\n• Repeat an expired search with one button\n• Choose another recording version\n• Shared collections and language across bot and app\n• Task queue, waiting, retry and cancellation\n• Reuse previously saved files\n• Menu, help and an owner-only admin panel')
}

_library_topic = TOPICS['library']
TOPICS['library'] = (*_library_topic[:2],
    _library_topic[2]+'\n\nИмпорт: пришли ссылку боту или открой «Моя музыка → Импорт плейлиста» в Mini App.\nПроверь список → «Добавить плейлист». Открой песню и выбери запись.\nБез ссылки: /import и список «Исполнитель — Название», по одной песне в строке.',
    _library_topic[3]+'\n\nImport: send a link to the bot or open My music → Import playlist in the Mini App.\nReview the list → Add playlist. Open a song and choose a recording.\nWithout a link: /import followed by Artist — Title, one song per line.')
