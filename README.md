
# WhatsApp AI Bot - Commercial Version

✅ Text + Voice message handling  
✅ Arabic & English support  
✅ OpenAI GPT-3.5 smart responses  
✅ Custom responses per client via `configs/phone_number.json`  
✅ Ready for production on Railway or Fly.io

## Setup
- Set environment variables:
  - OPENAI_API_KEY
  - WHATSAPP_TOKEN
  - VERIFY_TOKEN
  - PHONE_NUMBER_ID (in your webhook request context)

## Folder: configs/
Inside this folder, place a file for each client:
`configs/+966500000000.json`
```json
{
  "greeting": "مرحباً بك في مطاعم إبراهيم!",
  "custom_commands": {
    "menu": "🍽️ قائمة الطعام: بيتزا، برغر، عصير",
    "book": "☎️ للحجز اتصل على 0500000000",
    "location": "📍 الموقع: https://maps.app.goo.gl/xyz"
  }
}
```
