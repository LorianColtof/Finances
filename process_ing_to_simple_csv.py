import csv
import click


@click.command()
@click.option('--input-csv', '-i', required=True, type=click.File(mode='r'),
              help='Input CSV file')
@click.option('--output-csv', '-o', required=True, type=click.File(mode='w'),
              help='Output CSV file')
def main(input_csv, output_csv):
    reader = csv.DictReader(input_csv)
    writer = csv.DictWriter(output_csv, ['date', 'description', 'amount'])

    writer.writeheader()

    for row in reader:
        amount = float(row['Bedrag (EUR)'].replace('.', '').replace(',', '.'))
        if row['Af Bij'] == 'Af':
            amount *= -1

        description = '{} - {}'.format(row['Naam / Omschrijving'],
                                       row['Mededelingen'])
        date = row['Datum']

        writer.writerow({'date': date,
                         'description': description,
                         'amount': amount})

if __name__ == "__main__":
    main()
