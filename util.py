from collections import namedtuple
from enum import Enum
from typing import Optional, List
from datetime import date

Account = namedtuple('Account', ['name', 'value'])


class AssetAccounts(Enum):
    BANK_PAYMENT_ACCOUNT = 'Assets:Bank:Payment account'
    BANK_SAVINGS = 'Assets:Bank:Savings'
    BANK_CREDITCARD = 'Assets:Bank:Creditcard'
    INVESTMENT_FUND = 'Assets:Investment fund'


class ExpenseAccounts(Enum):
    FOOD_AND_GROCERIES = 'Expenses:Food and groceries'
    ALCOHOL = 'Expenses:Alcohol'
    PHONE_SUBSCRIPTION = 'Expenses:Phone:Subscription'
    DONATIONS = 'Expenses:Donations'
    PUBLIC_TRANSPORT = 'Expenses:Public transport'
    DOMAIN_NAME = 'Expenses:Domain name'
    RENT = 'Expenses:Room:Rent'
    HEALTH_INSURANCE = 'Expenses:Insurance:Health'
    LIABILITY_INSURANCE = 'Expenses:Insurance:Liability'
    OTHER_INSURANCE = 'Expenses:Insurance:Other'
    SPORT = 'Expenses:Sport'
    HAIRDRESSER = 'Expenses:Hairdresser'
    TUITION_FEES = 'Expenses:Tuition fees'
    TAX = 'Expenses:Tax'
    MISC = 'Expenses:Miscellaneous'


class IncomeAccounts(Enum):
    SALARY_SSL = 'Income:Salary:SSL Leiden'
    SALARY_HZFP = 'Income:Salary:Het Zwarte Fietsenplan'
    RENT_ALLOWANCE = 'Income:Allowance:Rent'
    HEALTH_ALLOWANCE = 'Income:Allowance:Health'
    GIFTS = 'Income:Gifts'
    REPAYMENTS = 'Income:Repayments'
    BOARD_GRANT = 'Income:Board grant'
    STUDENT_GRANTS_LOANS = 'Income:DUO student grants and loans'
    INVESTMENT_FUND_RETURN = 'Income:Investment fund return'
    OTHER = 'Income:Other'


class JournalEntry:
    def __init__(self, date: date, description: str) -> None:
        self.date = date
        self.description = description
        self.account1: Optional[Account] = None
        self.account2: Optional[Account] = None
        self.account3: Optional[Account] = None
        self.account4: Optional[Account] = None
        self.tags: List[str] = []

    def _check(self):
        if not (self.account1 and self.account2):
            raise ValueError(
                "At least account1 and account2 need to be present")

        s = self.account1.value + self.account2.value
        if self.account3:
            s += self.account3.value

        if self.account4:
            s += self.account4.value

        if s != 0:
            raise ValueError("Sum of account* values is not equal to zero.")

    @property
    def journal_str(self) -> str:
        self._check()

        s = "{} {}".format(self.date.strftime("%Y/%m/%d"), self.description)

        if self.tags:
            s += ";   "
            for t in self.tags:
                s += t + ": "

        s += "\n"

        for account in [self.account1, self.account2,
                        self.account3, self.account4]:
            if account:
                s += "    {:<40s}€{:.2f}\n".format(account.name.value,
                                                   account.value)

        s += "\n"
        return s

