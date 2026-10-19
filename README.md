# msynk-pjdsc-2026

## How to Run:
- Create a Virtual Environment `python -m venv ./venv`
- Activate Virtual Environment `venv\Scripts\activate`
- Install Requirements `pip install requirements.txt`
- Test pdf_reader.py `cd pdf_reader_module` `python pdf_reader.py`

## Project Structure:
```
app/
└── src/
    ├── components/         # Custom-built elements inside pages
    └── pages/              # Pages to be displayed in App

api/
├── core/
│   └── config.py           # API Config
    └── constants.py        # Application constants
│
├── middleware/
│   ├── auth.js            # JWT authentication
│   └── validation.js      # Input validation
│
├── models/
│   ├── Cart.js            # Cart schema
│   ├── Order.js           # Order schema
│   ├── Product.js         # Product schema
│   └── User.js            # User schema
│
├── routes/
│   ├── admin.js           # Admin routes
│   ├── auth.js            # Auth routes
│   ├── cart.js            # Cart routes
│   ├── orders.js          # Order routes
│   ├── products.js        # Product routes
│   └── users.js           # User routes
│
├── seeds/
│   └── adminUser.js       # Admin user seeder
│
├── utils/
│   └── helpers.js         # Helper functions
│
├── .env                   # Environment variables
├── package.json           # Dependencies
└── server.js              # Entry point

```
