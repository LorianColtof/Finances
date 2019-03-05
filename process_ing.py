import os
import csv
import click
import re
import textwrap

from dateutil.parser import parse as parse_date
from datetime import date, datetime as dt
from typing import TextIO
from enum import Enum

from prompt_toolkit import prompt
from prompt_toolkit.completion import FuzzyWordCompleter
from prompt_toolkit.validation import Validator
from prompt_toolkit.styles import Style

from util import Account, AssetAccounts, ExpenseAccounts, MiscAccounts,
    IncomeAccounts, JournalEntry


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
            'stamppot',
            'boerenkool',
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
                            'Chupitos',
                            'Jeda Horeca',  # De Gieter
                            'HOTSHOTS',
                            'Bier',
                            'Wodka'):
                account2 = ExpenseAccounts.ALCOHOL

            elif self.match(description, 'Incasso Creditcard'):
                account2 = MiscAccounts.TRANSFER

            elif self.match(description, 'SIMYO'):
                account2 = ExpenseAccounts.PHONE_SUBSCRIPTION

            elif self.match(description, 'UNICEF'):
                account2 = ExpenseAccounts.DONATIONS

            elif self.match(description,
                            r'\bNS\b',
                            'OV-Chipkaart'):
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

            elif self.match(description, 'Infomedics'):
                account2 = ExpenseAccounts.DENTIST

            elif self.match(description,
                            r'H\s?&\s?M',
                            r'van\s?Haren'):
                account2 = ExpenseAccounts.CLOTHING

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
                account2 = IncomeAccounts.STUDENT_GRANTS

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
                                    list(IncomeAccounts) +
                                    list(MiscAccounts)]

                    accounts_dict = {e.value: e for e in
                                    list(AssetAccounts) +
                                    list(ExpenseAccounts) +
                                    list(IncomeAccounts) +
                                    list(MiscAccounts)]

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
