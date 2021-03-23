#!/usr/bin/env python

#   Copyright 2020 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

import argparse
import json
import logging
import sys

from prettytable import PrettyTable

from validations_libs.validation_actions import ValidationActions
from validations_libs import constants

DESCRIPTION = "Run, show or list Validations."
EPILOG = "Example: ./validation run --validation check-ftype,512e"
# PrettyTable
RED = "\033[1;31m"
GREEN = "\033[0;32m"
CYAN = "\033[36m"
RESET = "\033[0;0m"


class ValidationClient(argparse.ArgumentParser):
    """Validation client implementation class"""

    log = logging.getLogger(__name__ + ".ValidationClient")

    def __init__(self, description=DESCRIPTION, epilog=EPILOG):
        """Init validation parser"""
        super(ValidationClient, self).__init__(description=DESCRIPTION,
                                                  epilog=EPILOG)

    def _print_dict_table(self, data):
        """Print table from python dict with PrettyTable"""
        t = PrettyTable(border=True, header=True, padding_width=1)
        # Set Field name by getting the result dict keys
        try:
            t.field_names = data[0].keys()
            t.align = 'l'
        except KeyError:
            raise KeyError()
        for r in data:
            if r.get('Status_by_Host'):
                h = []
                for host in r['Status_by_Host'].split(', '):
                    _name, _status = host.split(',')
                    color = (GREEN if _status == 'PASSED' else RED)
                    _name = '{}{}{}'.format(color, _name, RESET)
                    h.append(_name)
                r['Status_by_Host'] = ', '.join(h)
            if r.get('Status'):
                status = r.get('Status')
                color = (CYAN if status in ['starting', 'running']
                         else GREEN if status == 'PASSED' else RED)
                r['Status'] = '{}{}{}'.format(color, status, RESET)
            t.add_row(r.values())
        print(t)

    def _print_tuple_table(self, data, status_col=None):
        """Print table from python Tuple with PrettyTable"""
        if isinstance(data, tuple):
            t = PrettyTable(border=True, header=True, padding_width=1)
            try:
                t.field_names = data[0]
                t.align = 'l'
            except KeyError:
                raise KeyError()
            for r in data[1]:
                if status_col:
                    _result = list(r)
                    try:
                        _status = _result[status_col]
                        color = (GREEN if _status == 'PASSED' else RED)
                        _result[status_col] = '{}{}{}'.format(color,
                                                              _status,
                                                              RESET)
                    except ValueError:
                        logging.warning('No status found.')
                    t.add_row(_result)
                else:
                    t.add_row(r)
            print(t)
        else:
            raise RuntimeError("Wrong data type.")

    def _write_output(self, output_log, results):
        """Write output log file as Json format"""
        with open(output_log, 'w') as output:
            output.write(json.dumps({'results': results}, indent=4,
                                    sort_keys=True))


class ValidationClientRun(ValidationClient):
    """Validation Run client implementation class"""

    log = logging.getLogger(__name__ + ".ValidationClientRun")

    def __init__(self, description=DESCRIPTION, epilog=EPILOG):
        """Init validation parser"""
        super(ValidationClientRun, self).__init__(description=DESCRIPTION,
                                                  epilog=EPILOG)

    def parser(self, parser):
        """Argument parser for validation run"""
        parser.add_argument('--inventory', '-i', type=str,
                            default="localhost",
                            help="Path of the Ansible inventory.")
        parser.add_argument('--extra-vars', action='store',
                            nargs='+',
                            help="Extra ansible variables")
        parser.add_argument('--validation', '-v',
                            metavar='<validation_id>[,<validation_id>,...]',
                            dest="validation_name",
                            action=_CommaListAction,
                            default=[],
                            help=("Run specific validations, "
                                  "if more than one validation is required "
                                  "separate the names with commas: "
                                  "--validation check-ftype,512e | "
                                  "--validation 512e"))
        parser.add_argument('--group', '-g',
                            metavar='<group>[,<group>,...]',
                            action=_CommaListGroupAction,
                            default=[],
                            help=("Run specific group validations, "
                                  "if more than one group is required "
                                  "separate the group names with commas: "
                                  "--group pre-upgrade,prep | "
                                  "--group openshift-on-openstack"))
        parser.add_argument('--quiet', action='store_true',
                            help=("Run Ansible in silent mode."))
        parser.add_argument('--validation-dir', dest='validation_dir',
                            default=constants.ANSIBLE_VALIDATION_DIR,
                            help=("Path where the validation playbooks "
                                  "is located."))
        parser.add_argument('--ansible-base-dir', dest='ansible_base_dir',
                            default=constants.DEFAULT_VALIDATIONS_BASEDIR,
                            help=("Path where the ansible roles, library "
                                  "and plugins is located."))
        parser.add_argument('--output-log', dest='output_log',
                            default=None,
                            help=("Path where the run result will be stored"))
        return parser.parse_args()

    def take_action(self, parsed_args):
        """Take validation action"""
        # Get parameters:
        inventory = parsed_args.inventory
        group = parsed_args.group
        validation_name = parsed_args.validation_name
        quiet = parsed_args.quiet
        validation_dir = parsed_args.validation_dir
        ansible_base_dir = parsed_args.ansible_base_dir
        extra_vars = parsed_args.extra_vars
        if extra_vars:
            try:
                extra_vars = dict(e.split("=") for e in parsed_args.extra_vars)
            except ValueError:
                msg = "extra vars option should be formed as: KEY=VALUE."
                raise RuntimeError(msg)
        v_actions = ValidationActions(validation_path=validation_dir,
                                      group=group)
        try:
            results = v_actions.run_validations(
                inventory=inventory,
                group=group,
                validation_name=validation_name,
                base_dir=ansible_base_dir,
                extra_vars=extra_vars,
                quiet=quiet)
        except RuntimeError as e:
            sys.exit(e)
        if results:
            if parsed_args.output_log:
                self._write_output(parsed_args.output_log, results)
            else:
                self._print_dict_table(results)


class ValidationClientList(ValidationClient):
    """Validation List client implementation class"""

    log = logging.getLogger(__name__ + ".ValidationClientList")

    def __init__(self, description=DESCRIPTION, epilog=EPILOG):
        """Init validation parser"""
        super(ValidationClientList, self).__init__(description=DESCRIPTION,
                                                  epilog=EPILOG)

    def parser(self, parser):
        """Argument parser for validation run"""
        parser.add_argument('--group', '-g',
                            metavar='<group>[,<group>,...]',
                            action=_CommaListGroupAction,
                            default=[],
                            help=("Run specific group validations, "
                                  "if more than one group is required "
                                  "separate the group names with commas: "
                                  "--group pre-upgrade,prep | "
                                  "--group openshift-on-openstack"))
        parser.add_argument('--validation-dir', dest='validation_dir',
                            default=constants.ANSIBLE_VALIDATION_DIR,
                            help=("Path where the validation playbooks "
                                  "is located."))
        return parser.parse_args()

    def take_action(self, parsed_args):
        """Take validation action"""
        # Get parameters:
        group = parsed_args.group
        validation_dir = parsed_args.validation_dir

        v_actions = ValidationActions(validation_path=validation_dir,
                                      group=group)
        results = v_actions.list_validations()
        if results:
            if parsed_args.output_log:
                self._write_output(parsed_args.output_log, results)
            else:
                self._print_tuple_table(results)


class ValidationClientShow(ValidationClient):
    """Validation Show client implementation class"""

    log = logging.getLogger(__name__ + ".ValidationClientShow")

    def __init__(self, description=DESCRIPTION, epilog=EPILOG):
        """Init validation parser"""
        super(ValidationClientShow, self).__init__(description=DESCRIPTION,
                                                  epilog=EPILOG)

    def parser(self, parser):
        """Argument parser for validation show"""
        parser.add_argument('--group', '-g',
                            metavar='<group>[,<group>,...]',
                            action=_CommaListGroupAction,
                            default=[],
                            help=("Run specific group validations, "
                                  "if more than one group is required "
                                  "separate the group names with commas: "
                                  "--group pre-upgrade,prep | "
                                  "--group openshift-on-openstack"))
        parser.add_argument('--validation-dir', dest='validation_dir',
                            default=constants.ANSIBLE_VALIDATION_DIR,
                            help=("Path where the validation playbooks "
                                  "is located."))
        parser.add_argument('--validation', '-v',
                            metavar='<validation_id>[,<validation_id>,...]',
                            dest="validation_name",
                            action=_CommaListAction,
                            default=[],
                            help=("Run specific validations, "
                                  "if more than one validation is required "
                                  "separate the names with commas: "
                                  "--validation check-ftype,512e | "
                                  "--validation 512e"))
        return parser.parse_args()

    def take_action(self, parsed_args):
        """Take validation action"""
        # Get parameters:
        group = parsed_args.group
        validation_dir = parsed_args.validation_dir

        v_actions = ValidationActions(validation_path=validation_dir,
                                      group=group)
        results = v_actions.show_history(validation_name)
        if results:
            if parsed_args.output_log:
                self._write_output(parsed_args.output_log, results)
            else:
                self._print_tuple_table(data=results, status_col=2)


class ValidationClientHistory(ValidationClient):
    """Validation History client implementation class"""

    log = logging.getLogger(__name__ + ".ValidationClientShow")

    def __init__(self, description=DESCRIPTION, epilog=EPILOG):
        """Init validation parser"""
        super(ValidationClientHistory, self).__init__(description=DESCRIPTION,
                                                  epilog=EPILOG)

    def parser(self, parser):
        """Argument parser for validation history"""
        parser.add_argument('--validation-dir', dest='validation_dir',
                            default=constants.ANSIBLE_VALIDATION_DIR,
                            help=("Path where the validation playbooks "
                                  "is located."))
        parser.add_argument('--validation',
                            metavar="<validation>",
                            type=str,
                            help='Display execution history for a validation')

    def take_action(self, parsed_args):
        actions = ValidationActions(parsed_args.validation_dir)
        return actions.show_history(parsed_args.validation)
