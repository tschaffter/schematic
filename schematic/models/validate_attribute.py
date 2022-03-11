import builtins
from jsonschema import ValidationError
import logging
from numpy import full

# import numpy as np
import pandas as pd
import re
import sys
import os

# allows specifying explicit variable types
from typing import Any, Dict, Optional, Text, List
from urllib.parse import urlparse
from urllib.request import urlopen, OpenerDirector, HTTPDefaultErrorHandler
from urllib.request import Request
from urllib import error

from schematic.store.synapse import SynapseStorage
import synapseclient

import time

logger = logging.getLogger(__name__)


class GenerateError:
    def generate_list_error(
        list_string: str, row_num: str, attribute_name: str, list_error: str,
        invalid_entry:str,
    ) -> List[str]:
        """
            Purpose:
                If an error is found in the string formatting, detect and record
                an error message.
            Input:
                - list_string: the user input list, that is represented as a string.
                - row_num: the row the error occurred on.
                - attribute_name: the attribute the error occurred on.
            Returns:
                Logging.error.
                Errors: List[str] Error details for further storage.
            """
        if list_error == "not_comma_delimited":
            error_str = (
                f"For attribute {attribute_name} in row {row_num} it does not "
                f"appear as if you provided a comma delimited string. Please check "
                f"your entry ('{list_string}'') and try again."
            )
            logging.error(error_str)
            error_row = row_num  # index row of the manifest where the error presented.
            error_col = attribute_name  # Attribute name
            error_message = error_str
            error_val = invalid_entry
        return [error_row, error_col, error_message, error_val]

    def generate_regex_error(
        val_rule: str,
        reg_expression: str,
        row_num: str,
        module_to_call: str,
        attribute_name: str,
        invalid_entry:str,
    ) -> List[str]:
        """
            Purpose:
                Generate an logging error as well as a stored error message, when
                a regex error is encountered.
            Input:
                val_rule: str, defined in the schema.
                reg_expression: str, defined in the schema
                row_num: str, row where the error was detected
                module_to_call: re module specified in the schema
                attribute_name: str, attribute being validated
            Returns:
                Logging.error.
                Errors: List[str] Error details for further storage.
            """
        regex_error_string = (
            f"For the attribute {attribute_name}, on row {row_num}, the string is not properly formatted. "
            f'It should follow the following re.{module_to_call} pattern "{reg_expression}".'
        )
        logging.error(regex_error_string)
        error_row = row_num  # index row of the manifest where the error presented.
        error_col = attribute_name  # Attribute name
        error_message = regex_error_string
        error_val = invalid_entry
        return [error_row, error_col, error_message, error_val]

    def generate_type_error(
        val_rule: str, row_num: str, attribute_name: str, invalid_entry:str,
    ) -> List[str]:
        """
            Purpose:
                Generate an logging error as well as a stored error message, when
                a type error is encountered.
            Input:
                val_rule: str, defined in the schema.
                row_num: str, row where the error was detected
                attribute_name: str, attribute being validated
            Returns:
                Logging.error.
                Errors: List[str] Error details for further storage.
            """
        type_error_str = (
            f"On row {row_num} the attribute {attribute_name} "
            f"does not contain the proper value type {val_rule}."
        )
        logging.error(type_error_str)
        error_row = row_num  # index row of the manifest where the error presented.
        error_col = attribute_name  # Attribute name
        error_message = type_error_str
        error_val = invalid_entry
        return [error_row, error_col, error_message, error_val]

    def generate_url_error(
        url: str, url_error: str, row_num: str, attribute_name: str, argument: str,
        invalid_entry:str,
    ) -> List[str]:
        """
            Purpose:
                Generate an logging error as well as a stored error message, when
                a URL error is encountered.

                Types of errors included:
                    - Invalid URL: Refers to a URL that brings up an error when 
                        attempted to be accessed such as a HTTPError 404 Webpage Not Found.
                    - Argument Error: this refers to a valid URL that does not 
                        contain within it the arguments specified by the schema,
                        such as 'protocols.io' or 'dox.doi.org'
                    - Random Entry: this refers to an entry try that is not 
                        validated to be a URL.
                        e.g. 'lkejrlei', '0', 'not applicable'
            Input:
                url: str, that was input by the user.
                url_error: str, error detected in url_validation()
                attribute_name: str, attribute being validated
                argument: str, argument being validated.
            Returns:
                Logging.error.
                Errors: List[str] Error details for further storage.
            """
        error_row = row_num  # index row of the manifest where the error presented.
        error_col = attribute_name  # Attribute name
        if url_error == "invalid_url":
            invalid_url_error_string = (
                f"For the attribute '{attribute_name}', on row {row_num}, the URL provided ({url}) does not "
                f"conform to the standards of a URL. Please make sure you are entering a real, working URL "
                f"as required by the Schema."
            )
            logging.error(invalid_url_error_string)
            error_message = invalid_url_error_string
            error_val = invalid_entry
        elif url_error == "arg_error":
            arg_error_string = (
                f"For the attribute '{attribute_name}', on row {row_num}, the URL provided ({url}) does not "
                f"conform to the schema specifications and does not contain the required element: {argument}."
            )
            logging.error(arg_error_string)
            error_message = arg_error_string
            error_val = f"URL Error: Argument Error"
        elif url_error == "random_entry":
            random_entry_error_str = (
                f"For the attribute '{attribute_name}', on row {row_num}, the input provided ('{url}'') does not "
                f"look like a URL, please check input and try again."
            )
            logging.error(random_entry_error_str)
            error_message = random_entry_error_str
            error_val = f"URL Error: Random Entry"
        return [error_row, error_col, error_message, error_val]

    def generate_cross_error(
        val_rule: str,
        attribute_name: str,
        matching_manifests = [],
        manifest_ID = None,
        missing_entry = None,
        row_num = None,
    ) -> List[str]:
        """
            Purpose:
                Generate an logging error as well as a stored error message, when
                a cross validation error is encountered.
            Input:
                val_rule: str, defined in the schema.
                row_num: str, row where the error was detected
                attribute_name: str, attribute being validated
                missing_entry: str, value present in source manifest that is missing in the target
                manifest_ID: str, synID of the target manifest missing the source value
            Returns:
                Logging.error.
                Errors: List[str] Error details for further storage.
            """
        if val_rule.__contains__('matchAtLeast'):
            cross_error_str = (
                f"Manifest {manifest_ID} does not contain the value {missing_entry} "
                f"from row {row_num} of the attribute {attribute_name} in the source manifest."
            )
        elif val_rule.__contains__('matchExactly'):
            if matching_manifests != []:
                cross_error_str = (
                    f"All values from attribute {attribute_name} in the source manifest are present in {len(matching_manifests)} manifests instead of only 1. "
                    f"Manifests {matching_manifests} match the values in the source attribute."
                )
            else:
                cross_error_str = (
                    f"No matches for the values from attribute {attribute_name} in the source manifest are present in any other manifests instead of being present in exactly 1. "
                )

        logging.error(cross_error_str)
        error_row = row_num  # index row of the manifest where the error presented.
        error_col = attribute_name  # Attribute name
        error_message = cross_error_str
        error_val = missing_entry #Value from source manifest missing from targets
        
        return [error_row, error_col, error_message, error_val]



class ValidateAttribute(object):
    """
    A collection of functions to validate manifest attributes.
        list_validation
        regex_validation
        type_validation
        url_validation
        cross_validation
    See functions for more details.
    TODO:
        - Add year validator
        - Add string length validator
    """

    def list_validation(
        self, val_rule: str, manifest_col: pd.core.series.Series
    ) -> (List[List[str]], pd.core.frame.DataFrame):
        """
        Purpose:
            Determine if values for a particular attribute are comma separated.
        Input:
            - val_rule: str, Validation rule
            - manifest_col: pd.core.series.Series, column for a given attribute
        Returns:
            - manifest_col: Input values in manifest arere-formatted to a list
            - Error log, error list
        """

        # For each 'list' (input as a string with a , delimiter) entered,
        # convert to a real list of strings, with leading and trailing
        # white spaces removed.
        errors = []
        manifest_col = manifest_col.astype(str)
        # This will capture any if an entry is not formatted properly.
        for i, list_string in enumerate(manifest_col):
            if "," not in list_string and bool(list_string):
                list_error = "not_comma_delimited"
                errors.append(
                    GenerateError.generate_list_error(
                        list_string,
                        row_num=str(i+2),
                        attribute_name=manifest_col.name,
                        list_error=list_error,
                        invalid_entry=manifest_col[i]
                    )
                )
        # Convert string to list.
        manifest_col = manifest_col.apply(
            lambda x: [s.strip() for s in str(x).split(",")]
        )

        return errors, manifest_col

    def regex_validation(
        self, val_rule: str, manifest_col: pd.core.series.Series
    ) -> List[List[str]]:
        """
        Purpose:
            Check if values for a given manifest attribue conform to the reguar expression,
            provided in val_rule.
        Input:
            - val_rule: str, Validation rule
            - manifest_col: pd.core.series.Series, column for a given
                attribute in the manifest
            Using this module requres validation rules written in the following manner:
                'regex module regular expression'
                - regex: is an exact string specifying that the input is to be validated as a 
                regular expression.
                - module: is the name of the module within re to run ie. search. 
                - regular_expression: is the regular expression with which to validate
                the user input.
        Returns:
            - This function will return errors when the user input value
            does not match schema specifications.
            Logging.error.
            Errors: List[str] Error details for further storage.
        TODO: 
            move validation to convert step.
        """

        reg_exp_rules = val_rule.split(" ")

        try:
            module_to_call = getattr(re, reg_exp_rules[1])
            reg_expression = reg_exp_rules[2]
        except:
            raise ValidationError(
                f"The regex rules were not provided properly for attribute {manifest_col.name}."
                f" They should be provided as follows ['regex', 'module name', 'regular expression']"
            )

        errors = []
        # Handle case where validating re's within a list.
        if type(manifest_col[0]) == list:
            for i, row_values in enumerate(manifest_col):
                for j, re_to_check in enumerate(row_values):
                    re_to_check = str(re_to_check)
                    if not bool(module_to_call(reg_expression, re_to_check)) and bool(
                        re_to_check
                    ):
                        errors.append(
                            GenerateError.generate_regex_error(
                                val_rule,
                                reg_expression,
                                row_num=str(i + 2),
                                module_to_call=reg_exp_rules[1],
                                attribute_name=manifest_col.name,
                                invalid_entry=manifest_col[i]
                            )
                        )
        # Validating single re's
        else:
            manifest_col = manifest_col.astype(str)
            for i, re_to_check in enumerate(manifest_col):
                if not bool(module_to_call(reg_expression, re_to_check)) and bool(
                    re_to_check
                ):
                    errors.append(
                        GenerateError.generate_regex_error(
                            val_rule,
                            reg_expression,
                            row_num=str(i + 2),
                            module_to_call=reg_exp_rules[1],
                            attribute_name=manifest_col.name,
                            invalid_entry=manifest_col[i]
                        )
                    )

        return errors

    def type_validation(
        self, val_rule: str, manifest_col: pd.core.series.Series
    ) -> List[List[str]]:
        """
        Purpose:
            Check if values for a given manifest attribue are the same type
            specified in val_rule.
        Input:
            - val_rule: str, Validation rule, specifying input type, either
                'float', 'int', 'num', 'str'
            - manifest_col: pd.core.series.Series, column for a given
                attribute in the manifest
        Returns:
            -This function will return errors when the user input value
            does not match schema specifications.
            Logging.error.
            Errors: List[str] Error details for further storage.
        TODO:
            Convert all inputs to .lower() just to prevent any entry errors.
        """

        errors = []
        # num indicates either a float or int.
        if val_rule == "num":
            for i, value in enumerate(manifest_col):
                if bool(value) and not isinstance(value, (int, float)):
                    errors.append(
                        GenerateError.generate_type_error(
                            val_rule,
                            row_num=str(i + 2),
                            attribute_name=manifest_col.name,
                            invalid_entry=manifest_col[i]
                        )
                    )
        elif val_rule in ["int", "float", "str"]:
            for i, value in enumerate(manifest_col):
                if bool(value) and type(value) != getattr(builtins, val_rule):
                    errors.append(
                        GenerateError.generate_type_error(
                            val_rule,
                            row_num=str(i + 2),
                            attribute_name=manifest_col.name,
                            invalid_entry=manifest_col[i]
                        )
                    )
        return errors

    def url_validation(self, val_rule: str, manifest_col: str) -> List[List[str]]:
        """
        Purpose:
            Validate URL's submitted for a particular attribute in a manifest.
            Determine if the URL is valid and contains attributes specified in the
            schema.
        Input:
            - val_rule: str, Validation rule
            - manifest_col: pd.core.series.Series, column for a given
                attribute in the manifest
        Output:
            This function will return errors when the user input value
            does not match schema specifications.
        """

        url_args = val_rule.split(" ")[1:]
        errors = []

        for i, url in enumerate(manifest_col):
            # Check if a random phrase, string or number was added and
            # log the appropriate error.
            if not (
                urlparse(url).scheme
                + urlparse(url).netloc
                + urlparse(url).params
                + urlparse(url).query
                + urlparse(url).fragment
            ):
                #
                url_error = "random_entry"
                valid_url = False
                errors.append(
                    GenerateError.generate_url_error(
                        url,
                        url_error=url_error,
                        row_num=str(i + 2),
                        attribute_name=manifest_col.name,
                        argument=url_args,
                        invalid_entry=manifest_col[i]
                    )
                )
            else:
                # add scheme to the URL if not currently added.
                if not urlparse(url).scheme:
                    url = "http://" + url
                try:
                    # Check that the URL points to a working webpage
                    # if not log the appropriate error.
                    request = Request(url)
                    response = urlopen(request)
                    valid_url = True
                    response_code = response.getcode()
                except:
                    valid_url = False
                    url_error = "invalid_url"
                    errors.append(
                        GenerateError.generate_url_error(
                            url,
                            url_error=url_error,
                            row_num=str(i + 2),
                            attribute_name=manifest_col.name,
                            argument=url_args,
                            invalid_entry=manifest_col[i]
                        )
                    )
                if valid_url == True:
                    # If the URL works, check to see if it contains the proper arguments
                    # as specified in the schema.
                    for arg in url_args:
                        if arg not in url:
                            url_error = "arg_error"
                            errors.append(
                                GenerateError.generate_url_error(
                                    url,
                                    url_error=url_error,
                                    row_num=str(i + 2),
                                    attribute_name=manifest_col.name,
                                    argument=arg,
                                    invalid_entry=manifest_col[i]
                                )
                            )
        return errors


    
    def cross_validation(
        self, val_rule: str, manifest_col: pd.core.series.Series
    ) -> List[List[str]]:


        errors = []
        fully_present_in=0
        #parse sources and targets
        [source_component, source_attribute] = val_rule.split(" ")[1].split(".")
        [target_component, target_attribute] = val_rule.split(" ")[2].split(".")

        #synStore = SynapseStorage()
        #syn=synStore.login()
       
        access_token = os.getenv("SYNAPSE_ACCESS_TOKEN")
        syn = synapseclient.Synapse()     
        syn.login(authToken = access_token)

        #Get IDs of manifests with target component
        t1=time.time()

        target_IDs=self.get_target_manifests(target_component)
        
        t2=time.time()-t1

        print(f'Manifest Gathering Elapsed Time: {int(t2/60)}:{int(t2%60)}')
        missing_values = {}
        missing_manifest_log={}
        present_manifest_log=[]
        #Load each manifest
        for target_manifest_ID in target_IDs:
            entity = syn.get(target_manifest_ID)
            target_manifest=pd.read_csv(entity.path)
            print(target_manifest_ID)
            print(target_manifest)

            #convert manifest column names into validation rule input format
            column_names={}
            for name in target_manifest.columns:
                column_names[name.replace(" ","").lower()]=name

            #If the manifest has the target attribute for the component do the cross validation

            
            if target_attribute.lower() in column_names:
                target_column = target_manifest[column_names[target_attribute.lower()]]

                #Do the validation on both columns
                missing_values = manifest_col[~manifest_col.isin(target_column)]
                if missing_values.empty:
                    fully_present_in+=1
                    present_manifest_log.append(target_manifest_ID)
                else:
                    missing_manifest_log[target_manifest_ID] = missing_values


            #else:
            #    print("Attribute not found in manifest")

        if val_rule.__contains__('matchAtLeastOne') and len(present_manifest_log) < 1:
            #generate errors if necessary
            for row, value in zip (missing_values.keys(),missing_values):
                row = row +2 
                errors.append(
                    GenerateError.generate_cross_error(
                        val_rule = val_rule,
                        row_num = str(row),
                        attribute_name = source_attribute,
                        missing_entry = str(value),
                        manifest_ID = str(target_manifest_ID),
                    )
                )
        elif val_rule.__contains__('matchExactlyOne') and len(present_manifest_log) != 1:
            #generate errors if necessary
            errors.append(
                GenerateError.generate_cross_error(
                    val_rule = val_rule,
                    attribute_name = source_attribute,
                    manifest_ID = str(target_manifest_ID),
                    matching_manifests=present_manifest_log,
                )
            )
            

        return errors


