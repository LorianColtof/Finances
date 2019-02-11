import click
import csv
from datetime import datetime as dt
from dateutil.parser import parse as parse_date

from typing import TextIO

from util import Account, AssetAccounts, IncomeAccounts, JournalEntry


class CSVProcessor:
    def __init__(self, input_csv: TextIO, output_journal: TextIO) -> None:
        self.input_csv = input_csv
        self.output_journal = output_journal

    def process(self):
        reader = csv.DictReader(self.input_csv)

        now = dt.now().strftime("%Y-%m-%d %H:%m:%S")
        self.output_journal.write(
            f"; journal created on {now} by CSV import script\n\n")

        raw_entries = []

        for row in reader:
            date = parse_date(row['Date'])
            value = float(row['Value'].replace('.', '').replace(',', '.'))

            raw_entries.append((date, value))

        entries = sorted(raw_entries, key=lambda x: x[0])
        last_value = entries[0][1]

        print(f"Initial value: €{last_value}")

        transaction_id = 0
        for date, value in entries[1:]:
            diff_value = value - last_value
            last_value = value

            full_trans_id = '{}-M-{}'.format(date.year, transaction_id)

            date_str = date.strftime("%Y-%m-%d")
            entry = JournalEntry(date,
                                 f'{full_trans_id} - ' +
                                 f'Meesman value update {date_str}')
            entry.account1 = Account(
                AssetAccounts.INVESTMENT_FUND, diff_value)
            entry.account2 = Account(
                IncomeAccounts.INVESTMENT_FUND_RETURN, -diff_value)

            self.output_journal.write(entry.journal_str)

            transaction_id += 1


@click.command()
@click.option('--input-csv', '-i', required=True, type=click.File(mode='r'),
              help='Input CSV file')
@click.option('--output-journal', '-o', required=True,
              type=click.File(mode='w'), help='Output hledger journal file')
def main(input_csv, output_journal):

    p = CSVProcessor(input_csv, output_journal)
    p.process()


if __name__ == "__main__":
    main()
