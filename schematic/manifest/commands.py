#!/usr/bin/env python3

import click
import pandas as pd

from schematic.manifest.generator import ManifestGenerator
from schematic.utils.cli_utils import fill_in_from_config, query_dict
from schematic import CONFIG

CONTEXT_SETTINGS = dict(help_option_names=['--help', '-h'])  # help options

# invoke_without_command=True -> forces the application not to show aids before losing them with a --h
@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
def manifest(): # use as `schematic manifest ...`
    """
    Sub-commands with Manifest Generation utilities/methods.
    """
    pass


# prototype based on getModelManifest() and get_manifest()
# use as `schematic config get positional_args --optional_args`
@manifest.command('get', short_help='Prepares the manifest URL based on provided schema.')
# define the optional arguments
@click.option('-t', '--title', help='Title of generated manifest file.')
@click.option('-dt', '--data_type', help='Data type/component from JSON-LD schema to be used for manifest generation.')
@click.option('-p', '--jsonld', help='Path to JSON-LD schema.')
@click.option('-d', '--dataset_id', help='SynID of existing dataset on Synapse.')
@click.option('-s', '--sheet_url', is_flag=True, help='Enable/disable URL generation.')
@click.option('-a', '--use_annotations', is_flag=True, help='Include existing annotations.')
@click.option('-j', '--json_schema', help='Path to JSON Schema (validation schema).')
@click.option('-c', '--config', help='Path to schematic configuration file.', required=True)
def get_manifest(title, data_type, jsonld, dataset_id, sheet_url,
                 use_annotations, json_schema, config):
    """
    Running CLI with manifest generation options.
    """
    config_data = CONFIG.load_config(config)

    # optional parameters that need to be passed to ManifestGenerator()
    # can be read from config.yml as well
    title = fill_in_from_config(
        "title", title, ("manifest", "title")
    )
    data_type = fill_in_from_config(
        "data_type", data_type, ("manifest", "data_type")
    )
    jsonld = fill_in_from_config(
        "jsonld", jsonld, ("model", "input", "location")
    )
    json_schema = fill_in_from_config(
        "json_schema", json_schema, ("model", "input", "validation_schema")
    )

    # create object of type ManifestGenerator
    manifest_generator = ManifestGenerator(title=title,
                                           path_to_json_ld=jsonld,
                                           root=data_type)

    # call get_manifest() on manifest_generator
    result = manifest_generator.get_manifest(dataset_id=dataset_id,
                                             sheet_url=sheet_url,
                                             use_annotations=use_annotations,
                                             json_schema=json_schema)

    if sheet_url:
        click.echo(result)
    elif isinstance(result, pd.DataFrame):
        click.echo()
        click.echo(result.to_csv(index=False))
    return result
