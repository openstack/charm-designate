# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import mock

sys.path.append('src')
sys.path.append('src/lib')

# Mock out charmhelpers so that we can test without it.
import charms_openstack.test_mocks  # noqa
charms_openstack.test_mocks.mock_charmhelpers()
sys.modules['charmhelpers.core.decorators'] = (
    charms_openstack.test_mocks.charmhelpers.core.decorators)


def _fake_retry(num_retries, base_delay=0, exc_type=Exception):
    def _retry_on_exception_inner_1(f):
        def _retry_on_exception_inner_2(*args, **kwargs):
            return f(*args, **kwargs)
        return _retry_on_exception_inner_2
    return _retry_on_exception_inner_1

mock.patch(
    'charmhelpers.core.decorators.retry_on_exception',
    _fake_retry).start()
