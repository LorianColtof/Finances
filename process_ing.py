import os
import csv
import click
import re
import textwrap

from dateutil.parser import parse as parse_date
from datetime import date, datetime as dt
from collections import namedtuple
from typing import Optional, List, TextIO
from enum import Enum

from prompt_toolkit import prompt
from prompt_toolkit.completion import FuzzyWordCompleter
from prompt_toolkit.validation import Validator
from prompt_toolkit.styles import Style

Account = namedtuple('Account', ['name', 'value'])


class AssetAccounts(Enum):
    BANK_PAYMENT_ACCOUNT = 'Assets:Bank:Payment account'
    BANK_SAVINGS = 'Assets:Bank:Savings'
    BANK_CREDITCARD = 'Assets:Bank:Creditcard'


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


class TrackingFile:
    def __init__(self, import_filename):
        self.import_filename = import_filename
        self.fn = '.import_csv_tracking'

        if os.path.isfile(self.fn):
            with open(self.fn, 'r') as f:
                values = {s[0]: int(s[1])
                          for s in (l.strip().split(':')
                          for l in f)}
                self._current_id = values[import_filename] \
                    if import_filename in values else -1
        else:
            self._current_id = -1
            with open(self.fn, 'w') as f:
                f.write('{}:{}\n'.format(self.import_filename,
                                         self._current_id))

    @property
    def current_id(self):
        return self._current_id

    @current_id.setter
    def current_id(self, value):
        self._current_id = value
        data = ""
        with open(self.fn, 'r+') as f:
            for line in f:
                if line.startswith(self.import_filename):
                    data += "{}:{}\n".format(self.import_filename, value)
                else:
                    data += line

            f.seek(0)
            f.truncate()
            f.write(data)


class CSVProcessor:

    def __init__(self, input_csv: TextIO, output_journal: TextIO) -> None:
        self.input_csv = input_csv
        self.output_journal = output_journal
        self.tracking_file = TrackingFile(input_csv.name)

    def process(self):
        reader = csv.DictReader(self.input_csv)

        now = dt.now().strftime("%Y-%m-%d %H:%m:%S")
        if self.tracking_file.current_id == -1:
            self.output_journal.write(
                f"; journal created on {now} by CSV import script\n\n")
        else:
            self.output_journal.write(
                f"; journal continued on {now} by CSV import script\n\n")

        self.output_journal.flush()

        raw_entries = []

        for row in reader:
            amount = float(row['Bedrag (EUR)']
                           .replace('.', '').replace(',', '.'))
            if row['Af Bij'] == 'Af':
                amount *= -1

            date = parse_date(row['Datum'])
            raw_entries.append((date, amount,
                                row['Naam / Omschrijving'],
                                row['Mededelingen']))

        self.unknown_count = 0
        transaction_id = self.tracking_file.current_id + 1

        # Process the entries ordened by date
        for date, amount, name, comment in sorted(
                raw_entries, key=lambda e: e[0])[
                    transaction_id:]:

            entry = self.convert_transaction(amount, name, comment, date,
                                             transaction_id)
            self.output_journal.write(entry.journal_str)
            self.output_journal.flush()

            self.tracking_file.current_id = transaction_id
            transaction_id += 1

        print("Amount unknown: {}".format(self.unknown_count))

    def match(self, s, *args):
        reg = re.compile('.*(' + '|'.join(args) + ').*', re.IGNORECASE)
        return reg.match(s) is not None

    def convert_transaction(self, amount: float, name: str, comment: str,
                            date: date, transaction_id: int) -> JournalEntry:

        description = '{} - {}'.format(name, comment)
        full_trans_id = '{}-{}'.format(date.year, transaction_id)

        click.echo(click.style("Processing transaction ", fg='white') +
                   click.style(f"{full_trans_id}", fg='green', bold=True))

        short_description = textwrap.shorten(
            description, 80, placeholder='...')

        click.echo("\tDate:         " + click.style("{}".format(
            date.strftime('%d-%m-%Y')), fg='blue', bold=True))
        click.echo("\tDescription:  " + click.style("{}".format(
            short_description), fg='blue', bold=True))
        click.echo("\tAmount:       " + click.style("€{:.2f}".format(amount),
                                                    fg='blue', bold=True))
        direction = click.style("Income", fg='green', bold=True) \
            if amount > 0 else \
            click.style("Expense", fg='red', bold=True)

        click.echo("\tDirection:    " + direction)

        entry = JournalEntry(date, '{} - {}'.format(
            full_trans_id, description))
        account1: Enum = AssetAccounts.BANK_PAYMENT_ACCOUNT

        ask = False
        unknown = False

        food_keywords = [
            'eten',
            'gnocchi',
            'pasta',
            'wraps',
            'thais',
            'indiaas',
            'roti',
            'pizza',
            'lasagne',
            'risotto',
            'chinees',
            'sushi',
            'wok'
        ]

        if self.match(description, 'spaarrekening'):
            account2: Enum = AssetAccounts.BANK_SAVINGS

        # === Expenses
        elif amount < 0:

            if self.match(description,
                          'Albert Heijn',
                          'AH to Go',
                          'AH togo',
                          'AH Station',
                          'Lidl',
                          'Jumbo',
                          'Dirk',
                          'Spar sciencepark',
                          'UvAScience',
                          'Fuameh',
                          'Smullers',
                          'McDonald(?:\'|\s)?s',
                          r'\bMcD\b',
                          'Broodzaak',
                          r"Julia'?s",
                          'Thuisbezorgd',
                          *food_keywords):
                account2 = ExpenseAccounts.FOOD_AND_GROCERIES

            elif self.match(description,
                            'VERENIGING INFORMATIEWETENSCH.AMSTERDAM'):

                account2 = ExpenseAccounts.FOOD_AND_GROCERIES
                if not self.match(description, 'Afschrijving POS'):
                    ask = True

            elif self.match(description,
                            'Maslow',
                            'DE HEEREN VAN AEMS',
                            'Gall & Gall',
                            'Jeda Horeca',  # De Gieter
                            'HOTSHOTS',
                            'Bier',
                            'Wodka'):
                account2 = ExpenseAccounts.ALCOHOL

            elif self.match(description, 'Incasso Creditcard'):
                account2 = AssetAccounts.BANK_CREDITCARD

            elif self.match(description, 'SIMYO'):
                account2 = ExpenseAccounts.PHONE_SUBSCRIPTION

            elif self.match(description, 'UNICEF'):
                account2 = ExpenseAccounts.DONATIONS

            elif self.match(description, r'\bNS\b'):
                account2 = ExpenseAccounts.PUBLIC_TRANSPORT

            elif self.match(description, 'Transip'):
                account2 = ExpenseAccounts.DOMAIN_NAME

            elif self.match(description, 'De Key') \
                    and self.match(description, 'huur'):
                account2 = ExpenseAccounts.RENT

            elif self.match(description, 'Zorgverzekering'):
                account2 = ExpenseAccounts.HEALTH_INSURANCE

            elif self.match(description, 'Verzekering', 'Verzekeraar'):
                account2 = ExpenseAccounts.OTHER_INSURANCE

            elif self.match(description, 'AEGON'):
                account2 = ExpenseAccounts.LIABILITY_INSURANCE

            elif self.match(description, 'Sportexpl.mij'):  # = USC
                account2 = ExpenseAccounts.SPORT

            elif self.match(description, 'Basic Kappers'):
                account2 = ExpenseAccounts.HAIRDRESSER

            elif self.match(description, 'Belastingdienst'):
                account2 = ExpenseAccounts.TAX

            elif self.match(description, 'Universiteit van Amsterdam') and \
                    abs(amount) >= 1900:
                account2 = ExpenseAccounts.TUITION_FEES

            elif self.match(description, 'Betaalverzoek'):
                account2 = ExpenseAccounts.FOOD_AND_GROCERIES
                ask = True

            elif self.match(description,
                            r'\bCafe\b',
                            'bier'):
                account2 = ExpenseAccounts.ALCOHOL
                ask = True

            else:
                account2 = ExpenseAccounts.MISC
                unknown = True

        # === Income
        else:
            if self.match(description, 'ST.STUDIEBEGELEIDING LDN'):
                account2 = IncomeAccounts.SALARY_SSL

            elif self.match(description, 'HET ZWARTE FIETSENPLAN'):
                account2 = IncomeAccounts.SALARY_HZFP

            elif self.match(description,
                            r'\bDUO\b',
                            'Dienst Uitvoering Onderwijs',
                            'Studiefinanciering'):
                account2 = IncomeAccounts.STUDENT_GRANTS_LOANS

            elif self.match(description, 'Huurtoeslag'):
                account2 = IncomeAccounts.RENT_ALLOWANCE

            elif self.match(description, 'Zorgtoeslag'):
                account2 = IncomeAccounts.HEALTH_ALLOWANCE

            elif self.match(description, 'Universiteit van Amsterdam'):
                account2 = IncomeAccounts.BOARD_GRANT

                if amount != 275:
                    ask = True

            elif self.match(description, 'Betaalverzoek') and \
                    self.match(description, *food_keywords):
                account2 = ExpenseAccounts.FOOD_AND_GROCERIES

            elif self.match(description, *food_keywords):
                account2 = ExpenseAccounts.FOOD_AND_GROCERIES
                ask = True

            else:
                account2 = IncomeAccounts.OTHER
                unknown = True

        if ask or unknown:
            click.echo("\n\tFull description:\n" + click.style("\t{}".format(
                '\n\t'.join(textwrap.wrap(description))),
                fg='blue', bold=True))

        if ask:
            click.echo(click.style("\n\tAutomatically processed as:",
                                   fg='cyan', bold=True))
            click.echo(click.style("\t" + account2.value, fg='yellow'))

            if not click.confirm('\n> ' + click.style(
                    'Is this correct?', fg='magenta', bold=True),
                    default=True):
                unknown = True

        elif unknown:
            click.echo(click.style(
                "\n\tCould not process transaction Automatically",
                fg='red', bold=True))

        if unknown:
            self.unknown_count += 1

            confirmed = False
            while not confirmed:

                if click.confirm('\n> ' + click.style(
                        'Do you want to enter the account manually',
                        fg='magenta', bold=True), default=True):

                    all_accounts = [e.value for e in
                                    list(AssetAccounts) +
                                    list(ExpenseAccounts) +
                                    list(IncomeAccounts)]

                    accounts_dict = {e.value: e for e in
                                     list(AssetAccounts) +
                                     list(ExpenseAccounts) +
                                     list(IncomeAccounts)}

                    completer = FuzzyWordCompleter(words=all_accounts)

                    validator = Validator.from_callable(
                        lambda e: not e.strip() or e in accounts_dict,
                        move_cursor_to_end=True,
                        error_message='Invalid account name')

                    style = Style.from_dict({
                        'text': 'ansiyellow',
                        'default': 'ansicyan',
                        'prompt_symbol': 'ansiwhite bold'
                    })

                    try:
                        account_str = prompt(
                            [('class:text', 'Enter the account '),
                             ('class:other', '['),
                             ('class:default', account2.value),
                             ('class:other', ']'),
                             ('class:prompt_symbol', ' > ')],
                            completer=completer,
                            validator=validator,
                            style=style,
                            validate_while_typing=False)

                    except KeyboardInterrupt:
                        continue

                    if account_str.strip():
                        account2 = accounts_dict[account_str]

                    break
                else:
                    click.echo(click.style(
                        'Marking the transaction with tag UNKNOWN_TRANSACTION',
                        fg='cyan', bold=True))
                    entry.tags.append('UNKNOWN_TRANSACTION')
                    break

            arrow = '-->' if amount < 0 else '<--'
            click.echo(click.style("\n\tProcessed as:",
                                   fg='cyan', bold=True))
            click.echo(click.style("\t{:<20s} {} {}".format(
                account1.value, arrow, account2.value), fg='yellow'))

        else:
            arrow = '-->' if amount < 0 else '<--'
            click.echo(click.style("\n\tAutomatically processed as:",
                                   fg='cyan', bold=True))
            click.echo(click.style("\t{:<20s} {} {}".format(
                account1.value, arrow, account2.value), fg='yellow'))

        print()

        entry.account1 = Account(name=account1, value=amount)
        entry.account2 = Account(name=account2, value=-amount)

        return entry


@click.command()
@click.option('--input-csv', '-i', required=True, type=click.File(mode='r'),
              help='Input CSV file')
@click.option('--output-journal', '-o', required=True,
              type=click.File(mode='a+'), help='Output hledger journal file')
def main(input_csv, output_journal):

    p = CSVProcessor(input_csv, output_journal)
    p.process()


if __name__ == "__main__":
    main()
