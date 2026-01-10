# Greenwashing Detective Project

This project is a prototype system for detecting potential ESG greenwashing risks.  
It integrates a LINE Bot interface with backend analysis logic and a MySQL database,  
allowing users to query companies and receive summarized ESG-related insights.

---

## Project Architecture (Overview)

- LINE Bot (Rich Menu + Message Interaction)
- Backend (Python / Flask)
- MySQL Database
- LLM-based text summarization (ESG focus)

---

## Requirements

- Python 3.10+
- MySQL 8.x
- LINE Messaging API account (for LINE Bot testing)

---

## Database Setup (Local)

### 1. Create database

```sql
CREATE DATABASE testdb;

2. Import schema (table structure)

mysql -u root -p testdb < db/schema.sql

3. Import seed data (demo data)
mysql -u root -p testdb < db/seed.sql

Environment Variables

Create a .env file based on .env.example and fill in your own credentials.

Example:
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=testdb

How to Run (Local)
pip install -r requirements.txt
python app.py

Notes

The LINE Bot currently focuses on summary-level ESG insights,
not full multi-year or full-dimension ESG dashboards.

Detailed ESG metrics are intended to be accessed via the web dashboard.
Status

 Database schema and seed data prepared (打勾)

 Local LINE Bot interaction demo(打勾)

 Cloud deployment (future work)

