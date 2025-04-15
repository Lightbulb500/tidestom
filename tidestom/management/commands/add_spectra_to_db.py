import os
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path  # Import pathlib

from django.core.management.base import BaseCommand
from django.conf import settings
from custom_code.models import TidesTarget as Target
from custom_code.models import TidesClassSubClass
from tom_dataproducts.models import DataProduct
from tidestom.tides_utils.target_utils import generate_spectrum_plot, add_spectrum_to_database

# Configure logging
logging.basicConfig(
    filename=f'/Users/pwise/4MOST/tides/tidestom/logs/add_spectra_to_db_{datetime.now().strftime("%Y%m%d%H%M%S")}.log',  # Replace with your desired logfile path
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

class Command(BaseCommand):
    help = 'Add spectra to the database and update auto classifications'

    def add_arguments(self, parser):
        parser.add_argument('--mock', action='store_true', help='Add spectra from mock database')
        parser.add_argument('--pipeline', action='store_true', help='Add spectra from pipeline results')
        parser.add_argument('--pipeline-results', type=str, help='Path to the pipeline results file')

    def handle(self, *args, **kwargs):
        if kwargs['mock']:
            self.add_spectra_from_mock_db()
        elif kwargs['pipeline']:
            pipeline_results_path = kwargs['pipeline_results']
            if not pipeline_results_path:
                logging.error("Pipeline results path must be provided when using --pipeline option")
                return
            self.add_spectra_from_pipeline(pipeline_results_path)
        else:
            logging.error("Either --mock or --pipeline option must be specified")

    def add_spectra_from_mock_db(self):
        test_data_dir = Path(settings.BASE_DIR) / 'data/spectra/test'
        test_data_dir.mkdir(parents=True, exist_ok=True)
        target_csv_path = os.path.join(settings.TEST_DIR, "mock_DB.csv")

        if not os.path.exists(target_csv_path):
            self.stdout.write(self.style.ERROR(f"Target CSV file not found at {target_csv_path}"))
            return

        dbdf = pd.read_csv(target_csv_path, index_col=0)
        targets = Target.objects.all()
        for target in targets:
            spectrum_file_path = os.path.join(settings.TEST_DIR, f'sims/l1_obs_joined_{target.name}.fits')
            if os.path.exists(spectrum_file_path):
                # Check if the spectrum already exists in the database
                spectrum_exists = DataProduct.objects.filter(target=target, data=spectrum_file_path).exists()
                if not spectrum_exists:
                    generate_spectrum_plot(target, spectrum_file_path)
                    logging.info(f'Successfully updated plots for target {target.name}')
                    result = add_spectrum_to_database(target, spectrum_file_path)
                    if 'Error' in result:
                        logging.error(result)
                    else:
                        logging.info(result)
                else:
                    logging.warning(f'Spectrum for target {target.name} already exists in the database')

                # Add or update automatic classifications
                logging.info(f'Checking auto classifications for target {target.name}')
                int_name = int(target.name)
                if int_name in dbdf.index:
                    logging.info(f'Found target {target.name} in the mock catalogue')

                    # Find all classifier names by looking for columns that match AutoClass_{classifier_name}
                    classifier_names = [
                        col.split('_', 1)[1] for col in dbdf.columns
                        if col.startswith('AutoClass_') and f'AutoClass_SubClass_{col.split("_", 1)[1]}' in dbdf.columns and f'AutoClassProb_{col.split("_", 1)[1]}' in dbdf.columns
                    ]

                    for classifier_name in classifier_names:
                        auto_class = dbdf.at[int_name, f'AutoClass_{classifier_name}']
                        auto_class_subclass = dbdf.at[int_name, f'AutoClass_SubClass_{classifier_name}']
                        auto_class_prob = dbdf.at[int_name, f'AutoClassProb_{classifier_name}']

                        if auto_class:
                            # Update the JSONField with the classification data
                            if not target.auto_tidesclassifications:
                                target.auto_tidesclassifications = {}

                            target.auto_tidesclassifications[classifier_name] = {
                                "class": auto_class,
                                "subclass": auto_class_subclass,
                                "probability": auto_class_prob,
                            }

                            logging.info(f'Added classification for {classifier_name} to target {target.name}')
                        else:
                            logging.warning(f'No classification found for {classifier_name} for target {target.name}')

                    # Save the updated target
                    target.save()
                    logging.info(f'Updated auto classifications for target {target.name}')
                else:
                    logging.warning(f'Target {target.name} not found in the mock catalogue')
            else:
                logging.warning(f'Spectrum file {spectrum_file_path} not found for target {target.name}')

    def add_spectra_from_pipeline(self, pipeline_results_path):
        pipeline_results = pd.read_csv(pipeline_results_path)

        for _, row in pipeline_results.iterrows():
            obj_name = row['obj_name']
            spectrum_file_path = row['spectrum_file']
            auto_class = row.get('auto_class_agg')
            auto_class_subclass = row.get('auto_class_subclass_agg')
            auto_class_prob = row.get('auto_class_prob_agg')

            target = Target.objects.filter(name=obj_name).first()
            if not target:
                logging.warning(f'Target {obj_name} not found in the database')
                continue

            if not spectrum_file_path or not os.path.exists(spectrum_file_path):
                logging.warning(f'Spectrum file {spectrum_file_path} not found for target {obj_name}')
                continue

            # Check if the spectrum already exists in the database
            spectrum_exists = DataProduct.objects.filter(target=target, data=spectrum_file_path).exists()
            if not spectrum_exists:
                generate_spectrum_plot(target, spectrum_file_path)
                logging.info(f'Successfully updated plots for target {target.name}')
                result = add_spectrum_to_database(target, spectrum_file_path)
                if 'Error' in result:
                    logging.error(result)
                else:
                    logging.info(result)
            else:
                logging.warning(f'Spectrum for target {target.name} already exists in the database')

            # Add or update automatic classification
            if auto_class:
                target.auto_tidesclass = auto_class

                # Retrieve the TidesClassSubClass instance using the correct field
                auto_class_subclass_instance = TidesClassSubClass.objects.filter(sub_class=auto_class_subclass).first()

                if auto_class_subclass_instance:
                    target.auto_tidesclass_subclass = auto_class_subclass_instance
                else:
                    logging.warning(f"Subclass '{auto_class_subclass}' not found in TidesClassSubClass for target {target.name}")

                target.auto_tidesclass_prob = auto_class_prob
                target.save()
                logging.info(f'Updated auto classification for target {target.name}')
            else:
                logging.warning(f'No auto classification found for target {target.name}')