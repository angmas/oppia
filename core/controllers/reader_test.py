# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = 'Sean Lip'

import unittest

from core.domain import exp_services
from core.domain import rights_manager
import feconf
import test_utils


@unittest.skipIf(feconf.PLATFORM != 'gae',
                 'login not implemented for non-GAE platform')
class ReaderPermissionsTest(test_utils.GenericTestBase):
    """Test permissions for readers to view explorations."""

    def setUp(self):
        """Before each individual test, create a dummy exploration."""
        super(ReaderPermissionsTest, self).setUp()

        self.first_editor_email = 'editor@example.com'
        self.first_editor_id = self.get_user_id_from_email(
            self.first_editor_email)

        self.register_editor(self.first_editor_email)

        self.exploration_id = 'eid'
        self.exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                self.first_editor_id, 'A title', 'A category',
                self.exploration_id, default_dest_is_end_state=True))

        exp_services.save_exploration(self.first_editor_id, self.exploration)

    def test_unpublished_explorations_are_invisible_to_logged_out_users(self):
        response = self.testapp.get(
            '/learn/%s' % self.exploration_id, expect_errors=True)
        self.assertEqual(response.status_int, 404)

    def test_unpublished_explorations_are_invisible_to_unconnected_users(self):
        self.login('person@example.com', is_admin=False)
        response = self.testapp.get(
            '/learn/%s' % self.exploration_id, expect_errors=True)
        self.assertEqual(response.status_int, 404)
        self.logout()

    def test_unpublished_explorations_are_invisible_to_other_editors(self):
        another_editor = 'another@example.com'

        another_exploration = exp_services.get_exploration_by_id(
            exp_services.create_new(
                another_editor, 'A title', 'A category', 'eid2'))
        exp_services.save_exploration(another_editor, another_exploration)

        self.login(another_editor, is_admin=False)
        response = self.testapp.get(
            '/learn/%s' % self.exploration_id, expect_errors=True)
        self.assertEqual(response.status_int, 404)
        self.logout()

    def test_unpublished_explorations_are_visible_to_their_editors(self):
        self.login(self.first_editor_email, is_admin=False)
        response = self.testapp.get('/learn/%s' % self.exploration_id)
        self.assertEqual(response.status_int, 200)
        self.assertIn('This is a preview', response.body)
        self.logout()

    def test_unpublished_explorations_are_visible_to_admins(self):
        self.login('admin@example.com', is_admin=True)
        response = self.testapp.get('/learn/%s' % self.exploration_id)
        self.assertEqual(response.status_int, 200)
        self.assertIn('This is a preview', response.body)
        self.logout()

    def test_published_explorations_are_visible_to_anyone(self):
        rights_manager.publish_exploration(
            self.first_editor_id, self.exploration_id)
        exp_services.save_exploration(self.first_editor_id, self.exploration)

        response = self.testapp.get(
            '/learn/%s' % self.exploration_id, expect_errors=True)
        self.assertEqual(response.status_int, 200)
        self.assertNotIn('This is a preview', response.body)


class ReaderControllerEndToEndTests(test_utils.GenericTestBase):
    """Test the reader controller using the sample explorations."""

    TAGS = [test_utils.TestTags.SLOW_TEST]

    def setUp(self):
        super(ReaderControllerEndToEndTests, self).setUp()

    def _submit_answer(self, answer):
        """Action representing submission of an answer to the backend."""
        url = '/learnhandler/transition/%s/%s' % (
            self.exploration_id, self.last_state_name)
        reader_dict = self.post_json(url, {
            'answer': answer, 'block_number': self.last_block_number,
            'handler': 'submit', 'params': self.last_params,
            'state_history': self.state_history,
        })

        self.last_block_number = reader_dict['block_number']
        self.last_params = reader_dict['params']
        self.last_state_name = reader_dict['state_name']
        self.state_history += [self.last_state_name]
        self.assertEqual(reader_dict['state_history'], self.state_history)

        return reader_dict

    def submit_and_compare(self, answer, expected_response):
        """Submits an answer and compares the output to a regex.

        `expected_response` will be interpreted as a regex string.
        """
        reader_dict = self._submit_answer(answer)
        self.assertRegexpMatches(
            reader_dict['oppia_html'], expected_response)
        return self

    def init_player(self, exploration_id, expected_title, expected_response):
        """Starts a reader session and gets the first state from the server.

        `expected_response` will be interpreted as a regex string.
        """
        exp_services.delete_demo(exploration_id)
        exp_services.load_demo(exploration_id)

        self.exploration_id = exploration_id

        reader_dict = self.get_json(
            '/learnhandler/init/%s' % self.exploration_id)

        self.last_block_number = reader_dict['block_number']
        self.last_params = reader_dict['params']
        self.last_state_name = reader_dict['state_name']
        self.state_history = [self.last_state_name]

        self.assertEqual(reader_dict['state_history'], self.state_history)
        self.assertRegexpMatches(reader_dict['oppia_html'], expected_response)
        self.assertEqual(reader_dict['title'], expected_title)

    def test_welcome_exploration(self):
        """Test a reader's progression through the default exploration."""
        self.init_player(
            '0', 'Welcome to Oppia!', 'do you know where the name \'Oppia\'')
        self.submit_and_compare(
            '0', 'In fact, the word Oppia means \'learn\'.')
        self.submit_and_compare('Finish', 'Check your spelling!')
        self.submit_and_compare(
            'Finnish', 'Yes! Oppia is the Finnish word for learn.')

    def test_parametrized_adventure(self):
        """Test a reader's progression through the parametrized adventure."""
        self.init_player(
            '6', 'Parameterized Adventure', 'Hello, brave adventurer')
        self.submit_and_compare(
            'My Name', 'Hello, I\'m My Name!.*get a pretty red')
        self.submit_and_compare(0, 'fork in the road')
        self.submit_and_compare('ne', 'Hello, My Name. You have to pay a toll')

    def test_binary_search(self):
        """Test the binary search (lazy magician) exploration."""
        self.init_player(
            '8', 'The Lazy Magician', 'How does he do it?')
        self.submit_and_compare('Dont know', 'town square')
        self.submit_and_compare(0, 'Is it')
        self.submit_and_compare(2, 'Do you want to play again?')
        self.submit_and_compare(1, 'how do you think he does it?')
        self.submit_and_compare('middle', 'what number the magician picked')
        self.submit_and_compare(0, 'try it out')
        self.submit_and_compare(10, 'best worst case')
        self.submit_and_compare(
            0, 'to be sure our strategy works in all cases')
        self.submit_and_compare(0, 'try to guess')
