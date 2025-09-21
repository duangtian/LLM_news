<<<<<<< HEAD
# LLM_news
=======
# LLM News - Automated Research Paper News Bot

## ภาพรวมโปรเจกต์

LLM News เป็นระบบอัตโนมัติที่ดึงข้อมูลงานวิจัยจากแหล่งต่างๆ สรุปเป็นข่าวภาษาไทย และโพสต์ใน Discord ทุกวันเวลา 20:00 (เขตเวลาเอเชีย/กรุงเทพ)

## คุณสมบัติหลัก


## ข้อกำหนดระบบ


## การติดตั้ง

### 1. Clone โปรเจกต์

```bash
git clone <repository-url>
cd llm_news
```

### 2. สร้าง Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt

# หมายเหตุ: scholarly library สำหรับ Google Scholar จะติดตั้งอัตโนมัติ
```

### 4. ตั้งค่า Environment Variables

สร้างไฟล์ `.env` ในโฟลเดอร์รูท:

```env
# Database Configuration
DATABASE_URL=sqlite:///llm_news.db

# Discord Configuration
DISCORD_WEBHOOK_URL=your_discord_webhook_url
# หรือ
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_channel_id

# API Keys (สำหรับ LLM Summarization)
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Schedule Configuration
POST_TIME=20:00
TIMEZONE=Asia/Bangkok

# Content Configuration
KEYWORDS_INCLUDE=machine learning,AI,deep learning,neural networks,computer vision,natural language processing
KEYWORDS_EXCLUDE=advertisement,spam,marketing
MAX_PAPERS_PER_DAY=5

# Summarization Configuration
SUMMARIZER_MODE=rule_based  # หรือ openai, anthropic
SUMMARY_MIN_LENGTH=150
SUMMARY_MAX_LENGTH=250
TLDR_MAX_LENGTH=2

# Source Configuration
ENABLE_ARXIV=true
ENABLE_CROSSREF=true
ENABLE_BIORXIV=false
ENABLE_SEMANTIC_SCHOLAR=false
ENABLE_GOOGLE_SCHOLAR=true

# Rate Limiting
RATE_LIMIT_ARXIV=10
RATE_LIMIT_CROSSREF=50
RATE_LIMIT_GOOGLE_SCHOLAR=5

# Google Scholar specific settings
MAX_PAPERS_GOOGLE_SCHOLAR=20
GOOGLE_SCHOLAR_DAYS_BACK=7
GOOGLE_SCHOLAR_USE_PROXY=false
ENABLE_SEMANTIC_SCHOLAR=false

# Rate Limiting
RATE_LIMIT_ARXIV=10
RATE_LIMIT_CROSSREF=50

# Debug/Development
DEBUG=false
DRY_RUN=false
LOG_LEVEL=INFO
```

## การใช้งาน

### 1. รันครั้งเดียว (Manual)

```bash
python app.py run
```

### 2. ทดสอบการเชื่อมต่อ

```bash
python app.py test
```

### 3. ดูสถานะ

```bash
python app.py status
```

### 4. เริ่มตัวจัดตารางเวลา

```bash
python app.py schedule
```

### 5. รันในโหมด Development

```bash
# รันในโหมด dry-run (ไม่โพสต์จริง)
DEBUG=true DRY_RUN=true python app.py run

# รันแบบ verbose
LOG_LEVEL=DEBUG python app.py run
```

## โครงสร้างโปรเจกต์

```
llm_news/
├── storage/                 # Database models และ operations
│   ├── models.py           # SQLAlchemy models
│   └── db.py              # Database manager และ repositories
├── fetchers/               # ดึงข้อมูลจากแหล่งต่างๆ
│   ├── base.py            # Base classes
│   ├── arxiv.py           # arXiv API integration
│   ├── crossref.py        # Crossref API integration
│   └── manager.py         # Fetcher management
├── pipeline/               # ประมวลผลข้อมูล
│   ├── normalize.py       # Data normalization
│   ├── filter_rank.py     # Filtering และ ranking
│   └── summarize.py       # Thai summarization
├── delivery/               # ส่งข้อมูลไป Discord
│   ├── formatter.py       # Format messages
│   └── discord_post.py    # Discord posting
├── tests/                  # Unit และ integration tests
├── config.py              # Configuration management
├── app.py                 # Main application
├── requirements.txt       # Python dependencies
└── README.md             # เอกสารนี้
```

## การปรับแต่ง

### คำสำคัญการกรอง

แก้ไขใน `.env`:
```env
KEYWORDS_INCLUDE=machine learning,AI,deep learning,computer vision,NLP
KEYWORDS_EXCLUDE=survey,review,tutorial
```

### การสรุปข้อมูล

เลือกโหมดการสรุป:

### เขตเวลาและตารางเวลา

```env
POST_TIME=20:00           # เวลาโพสต์ (24-hour format)
TIMEZONE=Asia/Bangkok     # เขตเวลา
```

### แหล่งข้อมูล

เปิด/ปิดแหล่งข้อมูล:
```env
ENABLE_ARXIV=true
ENABLE_CROSSREF=true
ENABLE_BIORXIV=false
ENABLE_GOOGLE_SCHOLAR=true
```

### การตั้งค่า Google Scholar

Google Scholar มีข้อจำกัดพิเศษ:
```env
# จำนวนกระดาษสูงสุดต่อครั้ง
MAX_PAPERS_GOOGLE_SCHOLAR=20

# ระยะเวลาย้อนหลัง (วัน)
GOOGLE_SCHOLAR_DAYS_BACK=7

# ใช้ proxy (แนะนำเพื่อหลีกเลี่ยงการถูกบล็อก)
GOOGLE_SCHOLAR_USE_PROXY=false

# อัตราการร้องขอ (ต่อวินาที)
RATE_LIMIT_GOOGLE_SCHOLAR=5
```

**หมายเหตุสำคัญ**: Google Scholar อาจบล็อกการค้นหาอัตโนมัติ หากพบปัญหา ให้:
1. ลดค่า `RATE_LIMIT_GOOGLE_SCHOLAR` 
2. เปิดใช้ `GOOGLE_SCHOLAR_USE_PROXY=true`
3. ลด `MAX_PAPERS_GOOGLE_SCHOLAR`

## การใช้งานขั้นสูง

### การรัน Tests

```bash
# รัน unit tests
python -m pytest tests/test_fetchers.py -v

# รัน integration tests
python -m pytest tests/test_integration.py -v

# รันทุก tests
python -m pytest tests/ -v
```

### การใช้ Database อื่น

สำหรับ PostgreSQL:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/llm_news
```

### การใช้ Docker

สร้าง `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "app.py", "schedule"]
```

### การ Deploy บน Server

1. **ใช้ systemd service** (Linux):

สร้าง `/etc/systemd/system/llm-news.service`:
```ini
[Unit]
Description=LLM News Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/llm_news
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python app.py schedule
Restart=always

[Install]
WantedBy=multi-user.target
```

เปิดใช้งาน:
```bash
sudo systemctl enable llm-news
sudo systemctl start llm-news
```

2. **ใช้ screen หรือ tmux**:
```bash
screen -S llm-news
cd /path/to/llm_news
python app.py schedule
# กด Ctrl+A+D เพื่อ detach
```

## การแก้ไขปัญหา

### ปัญหาทั่วไป

1. **Import errors**: ตรวจสอบ virtual environment และ dependencies
2. **Database errors**: ตรวจสอบ DATABASE_URL และสิทธิ์ไฟล์
3. **Discord errors**: ตรวจสอบ webhook URL หรือ bot token
4. **API rate limits**: ลดค่า rate limits ใน config

### Debug Mode

```bash
DEBUG=true LOG_LEVEL=DEBUG python app.py run
```

### ตรวจสอบ Logs

Logs จะถูกเขียนไปที่:

## การมีส่วนร่วม

1. Fork โปรเจกต์
2. สร้าง feature branch
3. Commit การเปลี่ยนแปลง
4. Push ไปยัง branch
5. สร้าง Pull Request

## License

MIT License - ดูไฟล์ LICENSE สำหรับรายละเอียด

## การช่วยเหลือ

หากมีปัญหาหรือข้อสงสัย:
1. ตรวจสอบ Issues ใน GitHub
2. สร้าง Issue ใหม่พร้อมรายละเอียดข้อผิดพลาด
3. ใส่ log messages และ configuration ที่เกี่ยวข้อง


**หมายเหตุ**: โปรเจกต์นี้พัฒนาเพื่อการศึกษาและใช้งานส่วนตัว กรุณาปฏิบัติตาม Terms of Service ของ APIs ที่ใช้งาน

ระบบอัตโนมัติสำหรับดึงข้อมูล Paper จากแหล่งต่างๆ สรุปเป็นภาษาไทย และโพสต์ขึ้น Discord ทุกวันเวลา 20:00 น. (Asia/Bangkok)

## ✨ คุณสมบัติ

- 🔍 **ดึงข้อมูล Paper** จาก arXiv, Crossref, bioRxiv/medRxiv
- 🤖 **สรุปเป็นภาษาไทย** ด้วย LLM หรือกติกาเบื้องต้น
- 🎯 **คัดกรองเนื้อหา** ตาม keyword และความเกี่ยวข้อง
- 📅 **โพสต์อัตโนมัติ** ทุกวันเวลา 20:00 น.
- 🚫 **ป้องกันเนื้อหาซ้ำ** ด้วยระบบ deduplication
- 📊 **รายงานข้อผิดพลาด** และ retry อัตโนมัติ

## 🚀 การติดตั้ง

### 1. Clone Repository

```bash
git clone <repository-url>
cd llm_news
```

### 2. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

### 3. ตั้งค่า Environment Variables

```bash
# คัดลอกไฟล์ตัวอย่าง
cp .env.example .env

# แก้ไขไฟล์ .env
notepad .env  # Windows
# หรือ nano .env  # Linux/Mac
```

### 4. ตั้งค่าฐานข้อมูล

```bash
python -c "from storage.db import init_database; init_database()"
```

## ⚙️ การตั้งค่า

### Discord Configuration

1. **Discord Bot**: สร้าง Bot ใน [Discord Developer Portal](https://discord.com/developers/applications)
2. **Webhook**: หรือสร้าง Webhook ในช่องที่ต้องการ
3. **ใส่ Token/URL** ในไฟล์ `.env`

### LLM Configuration

เลือกหนึ่งใน provider สำหรับการสรุป:

- **OpenAI**: ตั้งค่า `SUMMARIZER_MODE=openai` และใส่ `OPENAI_API_KEY`
- **Anthropic**: ตั้งค่า `SUMMARIZER_MODE=anthropic` และใส่ `ANTHROPIC_API_KEY`
- **Rule-based**: ตั้งค่า `SUMMARIZER_MODE=rule_based` (ไม่ต้อง API Key)

### Keywords Configuration

```env
# คำที่ต้องการ
KEYWORDS_INCLUDE=LLM,diffusion,machine learning,AI,computer vision

# คำที่ไม่ต้องการ
KEYWORDS_EXCLUDE=survey,review only,obsolete

# หมวดหมู่ arXiv
ARXIV_CATEGORIES=cs.AI,cs.CL,cs.LG,cs.CV
```

## 🏃‍♂️ การใช้งาน

### รันครั้งเดียว (ทดสอบ)

```bash
# รันแบบ dry run (ไม่โพสต์จริง)
python app.py --dry-run

# รันจริง
python app.py --run-once
```

### รันอัตโนมัติ

```bash
# เริ่ม scheduler
python app.py

# รันใน background (Linux/Mac)
nohup python app.py &

# หรือใช้ systemd/supervisor
```

### ตัวอย่างการใช้งาน CLI

```bash
# ดูสถานะ
python app.py --status

# ทดสอบ fetcher
python app.py --test-fetcher arxiv

# ทดสอบ Discord
python app.py --test-discord

# ดู log ล่าสุด
python app.py --logs
```

## 📁 โครงสร้างโปรเจกต์

```
llm_news/
├── fetchers/           # ดึงข้อมูลจากแหล่งต่างๆ
│   ├── arxiv.py
│   ├── crossref.py
│   └── base.py
├── pipeline/           # ประมวลผลข้อมูล
│   ├── normalize.py
│   ├── filter_rank.py
│   └── summarize.py
├── delivery/           # ส่งข้อมูลไป Discord
│   ├── discord_post.py
│   └── formatter.py
├── storage/            # จัดการฐานข้อมูล
│   ├── models.py
│   └── db.py
├── tests/              # ทดสอบ
├── config.py           # การตั้งค่า
├── app.py              # แอปหลัก
└── requirements.txt
```

## 🧪 การทดสอบ

```bash
# รันทดสอบทั้งหมด
pytest

# ทดสอบเฉพาะส่วน
pytest tests/test_fetchers.py
pytest tests/test_summarizer.py

# ทดสอบแบบ verbose
pytest -v tests/
```

## 📊 ตัวอย่างผลลัพธ์

### รูปแบบข้อความใน Discord

**Title:** "Diffusion Models ช่วยลดค่าใช้จ่ายการเทรน 40% บนงานภาพแพทย์"

**สรุป:** นักวิจัยพัฒนาวิธีใหม่ในการใช้ Diffusion Models สำหรับการประมวลผลภาพทางการแพทย์ โดยสามารถลดต้นทุนการเทรนได้ถึง 40% เมื่อเทียบกับวิธีแบบดั้งเดิม การวิจัยนี้ทดสอบกับภาพ X-Ray และ MRI พบว่าความแม่นยำยังคงอยู่ในระดับเดิม แต่เวลาในการเทรนลดลงอย่างมาก...

**TL;DR:** ลดต้นทุนเทรน AI ได้ 40% โดยไม่เสียความแม่นยำ แต่ยังจำเพาะกับภาพทางการแพทย์

**Authors:** A. Nguyen, B. Lee, et al.  
**Source:** arXiv (2025-09-20)  
**Tags:** diffusion, medical imaging, efficiency  
**Link:** https://arxiv.org/abs/2409.12345

## 🛠️ การแก้ไขปัญหา

### ปัญหาที่พบบ่อย

1. **Discord Token ไม่ถูกต้อง**
   ```bash
   python app.py --test-discord
   ```

2. **API Rate Limit**
   - ปรับค่า `RATE_LIMIT_*` ในไฟล์ `.env`
   - เพิ่มเวลา delay ระหว่าง request

3. **สรุปภาษาไทยไม่ถูกต้อง**
   - ตรวจสอบ LLM provider และ API key
   - ลองเปลี่ยน model หรือ prompt

4. **ไม่มี Paper ใหม่**
   - ตรวจสอบ keyword และ category
   - ปรับช่วงเวลาค้นหา (เพิ่ม `SEARCH_DAYS`)

### Logs และ Monitoring

```bash
# ดู log ล่าสุด
tail -f logs/llm_news.log

# ตรวจสอบ database
python -c "from storage.db import get_stats; print(get_stats())"
```

## 🔒 Security Notes

- เก็บ API keys ใน environment variables เท่านั้น
- ใช้ `.env` file และห้ามเอาเข้า git
- ตั้งค่า rate limits ให้เหมาะสม
- ใส่ลิงก์อ้างอิงต้นฉบับเสมอ

## 📄 License

MIT License - ใช้งานและแก้ไขได้อย่างอิสระ

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📞 Support

หากพบปัญหาหรือมีข้อเสนอแนะ กรุณา:
- เปิด Issue ใน GitHub
- ดูเอกสารใน Wiki
- ตรวจสอบ FAQ ด้านล่าง

---

**สร้างขึ้นด้วย ❤️ สำหรับชุมชน Research และ AI ในประเทศไทย**
>>>>>>> 778788e (feat: medium/news surfacing improvements, nasa fix, quotas, logging, workflow)
