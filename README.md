# Email to Real-Time Ledger (e2RTLedger)

*Turn your finance emails into a real-time, automated ledger for your company using advanced AI agents.*

This AI engineering project parses incoming finance-related emails—such as invoices, receipts, and payment notifications—and extracts key transaction details to automatically update a live financial ledger. Stay on top of your company's expenses, payments, and income without manual data entry.

## Software Architecture

![Software Architecture Diagram](./images/Ryan_E2LEDGER_INFRASTRUCTURE.png)

## AI Architecture

This project leverages **LangGraph agentic AI** with a sophisticated multi-agent system designed for precision and accuracy:

### Specialized AI Agents

- **Entity Extractor Agent**: Intelligently extracts structured ledger entities from unstructured email content
  - Vendor/merchant names
  - Transaction types (payment, invoice, receipt)
  - Transaction amounts and currencies
  - Transaction dates and reference numbers
  
- **Categorizer Agent**: Automatically classifies transactions into business categories
  - SaaS subscriptions and software licenses
  - Office supplies and equipment
  - Meals & Entertainment
  - Transport and travel expenses
  - Other miscellaneous business expenses

### Few-Shot Learning Enhancement

Both agents utilize **few-shot example prompting** to significantly enhance accuracy and precision. The system includes carefully curated examples that demonstrate proper entity extraction and categorization patterns, enabling the AI agents to better understand context and maintain consistency across diverse email formats and transaction types.

The agents work collaboratively through LangGraph's orchestration framework, ensuring accurate data extraction and classification while maintaining consistency across the entire transaction processing pipeline.

## Features

- **Secure Email Integration**: Connects securely to your email inbox via IMAP
- **AI-Powered Processing**: LangGraph agentic system with specialized extraction and categorization agents
- **Real-Time Updates**: Live ledger updates with WebSocket connections
- **Multi-Currency Support**: Handles various currencies and invoice formats
- **Interactive Dashboard**: Web interface to view and manage transactions
- **Smart Classification**: Automatic transaction categorization using AI with few-shot learning
- **OCR Processing**: Extract data from PDF invoices and image receipts

## Getting Started

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/ryanrahmadifa/e2RTLedger.git
   cd e2RTLedger
   ```
2. `docker compose up --build`

## Prerequisites

- Docker and Docker Compose
- Python 3.8+ (for backend)
- Node.js 18+ (for WebSocket server and frontend)
- OpenRouter API key (for AI-powered email classification)

## Installation

### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/your-username/e2RTLedger.git
cd e2RTLedger
docker compose up --build
```

### Configuration

Create a `.env` file in the root directory:

```env
# OpenRouter API Configuration
OPENROUTER_API_KEY=your-openrouter-api-key

# Email Configuration
EMAIL_HOST=imap.gmail.com
EMAIL_ACCOUNT=your-email@company.com
EMAIL_PASSWORD=your-app-password

# Database Configuration
DATABASE_URL=postgresql://ledger:ledgerpw@postgres:5432/ledgerdb
REDIS_HOST=redis

# FastAPI Configuration
FASTAPI_CLASSIFY_URL=http://fastapi:8000/classify/
FASTAPI_OCR_SUBMIT_URL=http://fastapi:8000/ocr_document/
FASTAPI_OCR_URL=http://fastapi:8000/ocr_result/
FASTAPI_REDIS_PUBLISH_URL=http://fastapi:8000/redis_publish/
NEXT_PUBLIC_SOCKET_URL=http://websocket:3001
```

## Usage

### Accessing the Web Interface

Once running, access the web interface at:
- **Local**: `http://localhost:3000`
- **Docker**: `http://localhost:3000`

### API Endpoints

- **GET /health/**
  Simple health check returning `{ "status": "ok" }`.

- **POST /redis_claim/**
  Checks if a fingerprint is in the Redis set (deduplication).
  Adds a fingerprint to Redis set; errors on duplicate (status 409).

- **POST /ocr_document/**
  Uploads a PDF/image file, processes OCR in background, returns task_id.

- **GET /ocr_result/{task_id}**
  Poll to get OCR result or error status for a document processing task.

- **POST /classify/**
  Core classification endpoint, accepts text, date, and fingerprint.
  Does deduplication via Redis set, then classifies email content, saves and publishes ledger entries.

## Supported Email Types

The system automatically detects and processes:

- **Invoices**: PayPal, Stripe, Square, bank statements
- **Receipts**: E-commerce confirmations, service payments
- **Payment Notifications**: Banking alerts, wire transfers
- **Subscription Billing**: SaaS services, recurring payments
- **Expense Reports**: Travel, meals, office supplies

## Transaction Categories

Automatically classifies transactions into:
- Meals & Entertainment
- Transport
- SaaS
- Travel
- Office
- Other

## Development

### Docker Services

The application includes these Docker services:

- **fastapi**: Main application server, python backend for OCR and AI classification
- **postgres**: PostgreSQL database for storing transactions
- **redis**: Redis for caching and real-time updates
- **websocket**: Node.js server for real-time updates
- **frontend**: Next.js web interface for viewing transactions
- **email_listener**: Background service to fetch and process emails

## Troubleshooting

### Common Issues

**Email Connection Failed**
- Verify IMAP settings and credentials
- Enable "App Passwords" for Gmail
- Check firewall and network settings

**AI Classification Errors**
- Verify OpenRouter API key is valid
- Check API usage limits
- Review email content for parsing issues

**Database Connection Issues**
- Ensure PostgreSQL is running
- Verify database credentials
- Check network connectivity

## License

This POC is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Email: mryanrahmadifa@gmail.com
- Issues: [GitHub Issues](https://github.com/ryanrahmadifa/e2rtledger/issues)
- Documentation: [Wiki](https://github.com/ryanrahmadifa/e2rtledger/)

## Roadmap

- [ ] Machine learning model training on custom data
- [ ] Integration with accounting software (QuickBooks, Xero)
- [ ] Advanced reporting and analytics
- [ ] Multi-company support
- [ ] API rate limiting and authentication
- [ ] Webhook notifications for new transactions

---

**Made with precision by Muhammad Ryanrahmadifa**