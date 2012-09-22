# Software License Agreement (BSD License)
#
# Copyright (c) 2008, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

import sqlite3

class TagsDb(object):
    def create_distro_table(db_name, distro_name):
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute('create table %s (deb_name text, docs_url text, location text, package text)' % distro_name)
        conn.commit()
        c.close()
    create_distro_table = staticmethod(create_distro_table)

    def __init__(self, db_name, distro_name):
        self.db_name = db_name
        self.distro_name = distro_name

    #Get all the tag locations for a list of stacks
    def get_stack_tags(self, stack_names):
        tags = {}
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        for name in stack_names:
            #Get all entries for a given deb
            c.execute('select * from %s where deb_name = ?' % self.distro_name, (name,))
            rows = c.fetchall()
            if len(rows) > 0:
                tags[name] = []
                for r in rows:
                    tags[name].append({'docs_url':r['docs_url'], 'location':r['location'], 'package':r['package']})
        conn.commit()
        c.close()
        return tags

    #Write new tag locations for a list of stacks
    def write_stack_tags(self, stack_name, tags):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        #First, we need to delete all the old entries for this stack
        c.execute('delete from  %s where deb_name = ?' % self.distro_name, (stack_name,))
        for tag in tags:
            c.execute('insert into %s (deb_name, docs_url, location, package) \
                      values (?, ?, ?, ?)' % self.distro_name, 
                                             (stack_name, 
                                             tag['docs_url'], 
                                             tag['location'],
                                             tag['package']))
        conn.commit()
        c.close()



