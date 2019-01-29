import csv
import click
from dateutil.parser import parse as parse_date
from datetime import date, datetime as dt
from collections import namedtuple
from typing import Optional
import re

Account = namedtuple('Account', ['name', 'value'])


unknown_count = 0


class JournalEntry:
    def __init__(self, date: date, description: str) -> None:
        self.date = date
        self.description = description
        self.account1: Optional[Account] = None
        self.account2: Optional[Account] = None
        self.account3: Optional[Account] = None
        self.account4: Optional[Account] = None

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

        s = "{} {}\n".format(self.date.strftime("%Y/%m/%d"), self.description)

        for account in [self.account1, self.account2,
                        self.account3, self.account4]:
            if account:
                s += "   {:<40s}€{:.2f}\n".format(account.name, account.value)

        s += "\n"
        return s


def match(s, *args):
    reg = re.compile('.*(' + '|'.join(args) + ').*', re.IGNORECASE)
    return reg.match(s) is not None


def convert_transaction(amount: float, name: str,
                        comment: str, date: date) -> JournalEntry:

    description = '{} - {}'.format(name, comment)
    entry = JournalEntry(date, description)
    account1 = 'Assets:Bank:Payment account'
    unk = False

    if match(description, 'spaarrekening'):
        account2 = 'Assets:Bank:Savings'

    # === Expenses
    elif amount < 0:

        if match(description, 'Albert Heijn', 'Spar sciencepark'):
            account2 = 'Expenses:Groceries'

        elif match(description, 'UvAScience'):
            account2 = 'Expenses:UvA:Canteen'

        elif match(description, 'VERENIGING INFORMATIEWETENSCH.AMSTERDAM'):
            account2 = 'Expenses:UvA:VIA'

        elif match(description, 'SIMYO'):
            account2 = 'Expenses:Phone:Subscription'

        elif match(description, 'UNICEF'):
            account2 = 'Expenses:Donations'

        elif match(description, 'NS(\w|-)'):
            account2 = 'Expenses:Public transport'

        elif match(description, 'Transip'):
            account2 = 'Expenses:Domain name'

        elif match(description, 'De Key') and match(description, 'huur'):
            account2 = 'Expenses:Room:Rent'

        elif match(description, 'Zorgverzekering'):
            account2 = 'Expenses:Insurance:Health'

        elif match(description, 'Verzekering', 'Verzekeraar'):
            account2 = 'Expenses:Insurance:Other'

        elif match(description, 'AEGON'):
            account2 = 'Expenses:Insurance:Liability'

        else:
            account2 = 'Expenses:Unknown'
            unk = True

    # === Income
    else:
        if match(description, 'ST.STUDIEBEGELEIDING LDN'):
            account2 = 'Income:Salary:SSL Leiden'

        elif match(description, 'HET ZWARTE FIETSENPLAN'):
            account2 = 'Income:Salary:Het Zwarte Fietsenplan'

        elif match(description, 'Huurtoeslag'):
            account2 = 'Income:Allowance:Rent'

        elif match(description, 'Zorgtoeslag'):
            account2 = 'Income:Allowance:Health'

        elif match(description, 'Betaalverzoek'):
            account2 = 'Income:Payment requests'

        else:
            account2 = 'Income:Unknown'
            unk = True

    if unk:
        # print(description)
        pass

        global unknown_count
        unknown_count += 1

    entry.account1 = Account(name=account1, value=amount)
    entry.account2 = Account(name=account2, value=-amount)

    return entry


@click.command()
@click.option('--input-csv', '-i', required=True, type=click.File(mode='r'),
              help='Input CSV file')
@click.option('--output-journal', '-o', required=True,
              type=click.File(mode='w'), help='Output hledger journal file')
def main(input_csv, output_journal):
    reader = csv.DictReader(input_csv)

    now = dt.now().strftime("%Y-%m-%d")
    output_journal.write(f"; journal created {now} by CSV import script\n\n")

    entries = []
    for row in reader:
        amount = float(row['Bedrag (EUR)'].replace('.', '').replace(',', '.'))
        if row['Af Bij'] == 'Af':
            amount *= -1

        date = parse_date(row['Datum'])
        entry = convert_transaction(amount, row['Naam / Omschrijving'],
                                    row['Mededelingen'], date)

        entries.append((date, entry))

    for _, entry in sorted(entries, key=lambda e: e[0]):
        output_journal.write(entry.journal_str)

    print(unknown_count)


if __name__ == "__main__":
    main()
