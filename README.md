# myownlist

Свой список доменов для sing-box. Коммит строки в `lists/myownlist.txt` →
GitHub Actions собирает `output/myownlist.srs` → шлёт в Telegram.

## Использование

Добавь домен в `lists/myownlist.txt` (один на строку, без `http://`), закоммить и запушь в `main`.
Workflow `.github/workflows/build.yml` сам:
1. соберёт `output/myownlist.srs`,
2. закоммитит его от имени `github-actions[bot]`,
3. пришлёт в Telegram список добавленных доменов + ссылку на файл.

## Настройка Telegram-бота

1. `@BotFather` в Telegram → `/newbot` → получить токен.
2. Написать боту любое сообщение, затем открыть
   `https://api.telegram.org/bot<TOKEN>/getUpdates` и взять `chat.id`.
3. В репозитории: Settings → Secrets and variables → Actions → New repository secret:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

## Подключение

**Роутер (Podkop / sing-box remote rule-set)** — обновляется сам, ничего руками делать не надо:

```json
{
  "type": "remote",
  "tag": "myownlist",
  "format": "binary",
  "url": "https://raw.githubusercontent.com/vaas1k/myownlist/main/output/myownlist.srs",
  "download_detour": "direct"
}
```

**macOS (sing-box/SFM)** — по приходу телеграм-уведомления вручную скачать
тот же raw-URL поверх текущего `myownlist.srs` и перезапустить sing-box.

## Версия sing-box

Компиляция `.srs` идёт образом `ghcr.io/sagernet/sing-box`, версия зафиксирована
в `SING_BOX_VERSION` (`.github/workflows/build.yml`). Если файл не грузится на
роутере/маке — там другая версия sing-box, поменяй тег на совпадающую.
