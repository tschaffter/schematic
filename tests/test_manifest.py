import os
import logging
import pytest

from schematic.manifest.generator import ManifestGenerator
from schematic.schemas.generator import SchemaGenerator
import pandas as pd

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)



@pytest.fixture(
    params=[
        (True, "Patient"),
        (False, "Patient"),
        (True, "BulkRNA-seqAssay"),
        (False, "BulkRNA-seqAssay"),
    ],
    ids=[
        "use_annotations-Patient",
        "skip_annotations-Patient",
        "use_annotations-BulkRNAseqAssay",
        "skip_annotations-BulkRNAseqAssay",
    ],
)
def manifest_generator(helpers, request):

    # Rename request param for readability
    use_annotations, data_type = request.param

    manifest_generator = ManifestGenerator(
        path_to_json_ld=helpers.get_data_path("example.model.jsonld"),
        root=data_type,
        use_annotations=use_annotations,
    )

    yield manifest_generator, use_annotations, data_type

    # Clean-up
    try:
        os.remove(helpers.get_data_path(f"example.{data_type}.schema.json"))
    except FileNotFoundError:
        pass

@pytest.fixture(params=[True, False], ids=["sheet_url", "data_frame"])
def manifest(dataset_id, manifest_generator, request):

    # Rename request param for readability
    sheet_url = request.param

    # See parameterization of the `manifest_generator` fixture
    generator, use_annotations, data_type = manifest_generator

    manifest = generator.get_manifest(dataset_id=dataset_id, sheet_url=sheet_url)

    yield manifest, use_annotations, data_type, sheet_url


class TestManifestGenerator:
    def test_init(self, helpers):

        generator = ManifestGenerator(
            title="mock_title",
            path_to_json_ld=helpers.get_data_path("example.model.jsonld"),
        )

        assert type(generator.title) is str
        # assert generator.sheet_service == mock_creds["sheet_service"]
        assert generator.root is None
        assert type(generator.sg) is SchemaGenerator

    @pytest.mark.google_credentials_needed
    def test_get_manifest_first_time(self, manifest):

        # See parameterization of the `manifest_generator` fixture
        output, use_annotations, data_type, sheet_url = manifest

        if sheet_url:
            logger.debug(output)
            assert isinstance(output, str)
            assert output.startswith("https://docs.google.com/spreadsheets/")
            return

        # Beyond this point, the output is assumed to be a data frame

        # Update expectations based on whether the data type is file-based
        is_file_based = data_type in ["BulkRNA-seqAssay"]

        assert "Component" in output
        assert is_file_based == ("eTag" in output)
        assert is_file_based == ("Filename" in output)
        assert (is_file_based and use_annotations) == ("confidence" in output)

        # Data type-specific columns
        assert (data_type == "Patient") == ("Diagnosis" in output)
        assert (data_type == "BulkRNA-seqAssay") == ("File Format" in output)

        # The rest of the tests have to do with a file-based data type
        if data_type != "BulkRNA-seqAssay":
            assert output.shape[0] == 1  # Number of rows
            return

        # Beyond this point, the output is to be from a file-based assay

        # Confirm contents of Filename column
        assert output["Filename"].tolist() == [
            "TestDataset-Annotations-v3/Sample_A.txt",
            "TestDataset-Annotations-v3/Sample_B.txt",
            "TestDataset-Annotations-v3/Sample_C.txt",
        ]

        # Test dimensions of data frame
        assert output.shape[0] == 3  # Number of rows
        if use_annotations:
            assert output.shape[0] == 3  # Number of rows
            assert "eTag" in output
            assert "confidence" in output
            assert output["Year of Birth"].tolist() == ["1980", "", ""]

        # An annotation merged with an attribute from the data model
        if use_annotations:
            assert output["File Format"].tolist() == ["txt", "csv", "fastq"]
      
    @pytest.mark.parametrize("output_format", [None, "dataframe", "excel", "google_sheet"])
    @pytest.mark.parametrize("sheet_url", [None, True, False])
    @pytest.mark.parametrize("dataset_id", [None, "syn27600056"])
    @pytest.mark.google_credentials_needed
    def test_get_manifest_excel(self, helpers, sheet_url, output_format, dataset_id):
        '''
        Purpose: the goal of this test is to make sure that output_format parameter and sheet_url parameter could function well; 
        In addition, this test also makes sure that getting a manifest with an existing dataset_id is working
        "use_annotations" and "data_type" are hard-coded to fixed values to avoid long run time
        '''

        data_type = "Patient"

        generator = ManifestGenerator(
        path_to_json_ld=helpers.get_data_path("example.model.jsonld"),
        root=data_type,
        use_annotations=False,
        )


        manifest= generator.get_manifest(dataset_id=dataset_id, sheet_url = sheet_url, output_format = output_format)

        # if dataset id exists, it could return pandas dataframe, google spreadsheet, or an excel spreadsheet
        if dataset_id: 
            if output_format: 

                if output_format == "dataframe":
                    assert isinstance(manifest, pd.DataFrame)
                elif output_format == "excel":
                    assert os.path.exists(manifest) == True
                else: 
                    assert type(manifest) is str
                    assert manifest.startswith("https://docs.google.com/spreadsheets/")
            else: 
                if sheet_url: 
                    assert type(manifest) is str
                    assert manifest.startswith("https://docs.google.com/spreadsheets/")
                else: 
                    assert isinstance(manifest, pd.DataFrame)
        
        # if dataset id does not exist, it could return an empty google sheet or an empty excel spreadsheet exported from google
        else:
            if output_format: 
                if output_format == "excel":
                    assert os.path.exists(manifest) == True
                else: 
                    assert type(manifest) is str
                    assert manifest.startswith("https://docs.google.com/spreadsheets/")
        
        # Clean-up
    
        if type(manifest) is str and os.path.exists(manifest): 
            os.remove(manifest)




