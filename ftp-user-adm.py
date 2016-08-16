#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import re
import sys
import subprocess
import random
import string
import argparse
import smtplib
import mysql.connector


# variables
mysql_user = 'ftpd'
mysql_pass = 'your_db_password'
mysql_db = 'ftpd'
mysql_host = 'localhost'

email_enable = False
email_server = 'mail.example.com'
email_ftp_admin = 'admin@example.com'
email_from = 'ftp@example.com'

ftp_server_host = 'ftp.example.com'

class FtpUser(object):
    def __init__(self, fullname, email, region, groups):
        self.fullname = fullname
        self.email = email
        self.region = region
        self.groups = groups

    # generates ftp username from full name
    # e.g. John Doe -> j_doe
    def generate_name(self):
        if self.fullname == '':
            print('No name and surname provided.')
            sys.exit(1)
        username = self.fullname.split(' ')
        for i in username:
            if i != re.match('[a-zA-Z]*', i).group():
                print('Only latin aphabet letters are allowed in'
                      'name/surname.')
                sys.exit(1)

        if len(username) == 1:
            return ''.join(username).lower()

        if len(username) == 2:
            username[0] = username[0][0]
            return '_'.join(username).lower()

        if len(username) > 2:
            print('You must enter only name and surname. Only 1 or 2 words.')
            sys.exit(1)

    # generates and hashes user password
    # uses: /bin/echo '{md5}'`/bin/echo -n 'password' |
    # openssl dgst -binary -md5 | openssl enc -base64`
    def generate_password(self):
        global unencrypted_password
        unencrypted_password = ''.join(random.choice(string.ascii_letters +
                                       string.digits +
                                       '!@#$%') for i in range(10))
        cmd = (
              "/bin/echo '{md5}'`/bin/echo -n '" +
              unencrypted_password +
              "' | openssl dgst -binary -md5 | openssl enc -base64`"
              )
        global password
        password = (
                   subprocess.check_output(cmd, shell=True)
                   .decode('ascii').strip()
                   )
        return password

    # checks for valid email format
    def check_email(self):
        match = re.match(r'[\w.-]+@[\w.-]+.\w', self.email)
        if match is None or match.group() != self.email:
            print('E-mail address format is not valid.')
            sys.exit(1)
        else:
            return self.email

    # checks if groups are separated by spaces
    # and if there are such groups in ftpgroup table
    def check_groups(self):
        # check if group hasn't typed more than once
        if sorted(self.groups.split()) != sorted(set(self.groups.split())):
            print("You have entered the same group more than once")
            sys.exit(1)
        # check if such a group exists
        for i in self.groups.split():
            if i not in self.list_groups():
                print('There is no such user group named: {}'.format(i))
                sys.exit(1)
        # check if group name contain only letters and are separated by spaces
        match = re.match(r'[a-zA-Z\s]+', self.groups)
        if match.group() == self.groups:
            return self.groups.split()
        else:
            print(
                 'Groups must be separated by space and contain only letters.'
                 )
            sys.exit(1)

    # inserts new user data in 'ftpuser' table
    def insert_user_sql(self):
        self.generate_name()
        self.check_email()
        self.check_groups()
        self.generate_password()
        query = (
                "INSERT INTO ftpuser "
                "(userid, passwd, homedir, shell, fullname, region, email) "
                "VALUES ('{}', '{}', '{}','{}', '{}', '{}', '{}')"
                .format(self.generate_name(),
                        password,
                        "/ftp",
                        "/sbin/nologin",
                        self.fullname,
                        self.region,
                        self.email)
                )

        self.mysql_query(query, "INSERT")
        print("User created successfuly.")

    # adds new user to groups in 'ftpgroup' table
    def insert_groups_sql(self):
        for i in self.check_groups():
            query = (
                    "UPDATE ftpgroup SET members = CONCAT(members, '{},') "
                    "WHERE groupname = '{}'"
                    .format(self.generate_name(), i)
                    )
            self.mysql_query(query, 'INSERT')

    # deletes user from 'ftpuser' table
    # and removes from added groups in 'ftpgroup' table
    def delete_user(self, username):
        self.username = username
        del_user_q = "DELETE FROM ftpuser WHERE userid = '{}'".format(username)
        if self.mysql_query(del_user_q, type='DELETE') == 0:
            print("User '{}' does not exist.".format(username))
            sys.exit(1)
        get_groups_list = (
                          "SELECT groupname FROM ftpgroup "
                          "WHERE members LIKE '%,{},%'"
                          .format(username)
                          )
        for i in self.mysql_query(get_groups_list, type='SELECT')[0]:
            update_groups = (
                            "UPDATE ftpgroup SET members = "
                            "REPLACE(members, '{},', '{}') "
                            "WHERE groupname = '{}'"
                            .format(username, '', i[0])
                            )
            self.mysql_query(update_groups, type='UPDATE')
        print('Done!')
        sys.exit(0)

    # delete group from 'ftpgroup' table
    def delete_group(self, group):
        self.group = group
        query = "DELETE FROM ftpgroup WHERE groupname = '{}'".format(group)
        if self.mysql_query(query, type='DELETE') == 0:
            print("There is no group named '{}'".format(group))
            sys.exit(1)
        print("Group {} successfully deleted.".format(group))
        sys.exit(0)

    # create new ftp group
    def create_group(self, group):
        if len(group.split()) != 1:
            print("Group name must be single word.")
        query = (
                "INSERT INTO ftpgroup (groupname, gid) VALUES ('{}', '5500')"
                .format(group.lower())
                )
        self.mysql_query(query, type='INSERT')
        print(
             "Group '{}' has been successfully created.".format(group.lower())
             )

    # show all groups
    def list_groups(self):
        query = "SELECT groupname FROM ftpgroup"
        all_groups = []
        for i in self.mysql_query(query, type='SELECT')[0]:
            all_groups += i
        return all_groups

    # show users from chosen group
    def show_group_users(self, group):
        query = (
                "SELECT members FROM ftpgroup WHERE groupname = '{}'"
                .format(group)
                )
        if self.mysql_query(query, type='SELECT')[1] >= 1:
            for i in self.mysql_query(query, type='SELECT')[0][0]:
                print(i)
        else:
            print('There is no group named: {}'.format(group))

    # returns list of groups where user belongs
    def show_user_group(self, username):
        self.username = username
        query = (
                "SELECT groupname FROM ftpgroup "
                "WHERE members LIKE '%{},%'"
                .format(username)
                )
        if self.mysql_query(query, type='SELECT')[1] >= 1:
            for i in self.mysql_query(query, type='SELECT')[0]:
                print(i[0])
        else:
            print('There is no user named: {}'.format(username))

    # queries db for user and displays found user info
    def show_user_info(self, user):
        user_query = (
                     "SELECT userid, fullname, email, "
                     "region, accessed, modified "
                     "FROM ftpuser WHERE userid LIKE '%{}%' "
                     "OR fullname LIKE '%{}%' "
                     "OR email LIKE '%{}%' "
                     "OR region LIKE '%{}%'".format(user, user, user, user)
                     )
        user_output = self.mysql_query(user_query, type="SELECT")
        if user_output[1] == 0:
            print('Found nothing.')
            sys.exit(0)
        for i in user_output[0]:
            group_query = (
                    "SELECT groupname FROM ftpgroup "
                    "WHERE members LIKE '%{}%'"
                    .format(i[0])
                    )
            group_output = self.mysql_query(group_query, type="SELECT")[0]
            group_res = ""
            # since group_output is tuple inside list [('test',), ('office',)]
            # it has to be converted to string
            for j in group_output:
                group_res += j[0] + " "
            print(
                 "\nUsername: {}\nFull Name: {}\nE-mail: {}\nRegion: {}\n"
                 "Accessed: {}\nModified: {}\nGroups: {}\n"
                 .format(i[0], i[1], i[2], i[3], i[4], i[5], group_res)
                 )

    # sends email to provided user e-mail address containing login info
    def send_email(self):
        msg = ("Subject: Your FTP account\n\nDear " + self.fullname +
               ",\nYour FTP account has been created:"
               "\n\n\tFTP server address: " + ftp_server_host + "\n"
               "\tusername: " + self.generate_name() + "\n\tpassword: " +
               unencrypted_password + "\n\nIf you have any issues, feel free "
               "to contact system administrator:" + ftp_email_admin + "\n"
               "This is automatically generated message. Do not reply."
               )
        try:
            mail = smtplib.SMTP(email_server)
            mail.sendmail(email_from, self.email, msg)
        except:
            print("Unable to send e-mail.")

    """ Template to query MySQL/MariaDB db returns *tuple* consisting of
    output of query as list and number or rows, when query type is SELECT
    e.g returns -> (['output', 'list'], 5)
    when query type is INSERT/UPDATE/DELETE etc. returns only affected
    number or rows.
    """
    def mysql_query(self, query, type):
        try:
            conn = mysql.connector.connect(
                            user=mysql_user,
                            password=mysql_pass,
                            database=mysql_db,
                            host=mysql_host
                            )
            cursor = conn.cursor(buffered=True)
            cursor.execute(query)
            if type.lower() == 'select':
                count = cursor.rowcount
                return (cursor.fetchall(), count)
            else:
                conn.commit()
                count = cursor.rowcount
                return count

        except mysql.connector.Error as e:
            print(e)
            sys.exit(1)
        else:
            cursor.close()
            conn.close()


parser = argparse.ArgumentParser(description='Add, search or modify ProFTPd '
                                             'virtual users.')
subparsers = parser.add_subparsers(title='command', dest='command')

# create subcommand
parser_create = subparsers.add_parser('create', help='Add new user or group')
subparsers_create = parser_create.add_subparsers(dest='sub_command')

parser_create_user = subparsers_create.add_parser('user', help='Add new user')
parser_create_user.add_argument('-n', '--name',
                                metavar='Name Surname',
                                required=True,
                                help='User realname. In case you enter'
                                     'single name - '
                                     'username will be generated as this name.'
                                     'If you enter Name Surname then user will'
                                     'be generated as n_surname. Does not '
                                     'support realname that is  3 or more'
                                     'words.')
parser_create_user.add_argument('-e', '--email',
                                metavar='email address',
                                required=True,
                                help='Email address to which login info will'
                                     'be sent')
parser_create_user.add_argument('-r', '--region',
                                metavar='region',
                                required=True,
                                help='Describe where user comes from: '
                                     'country/city/mall etc')
parser_create_user.add_argument('-g', '--groups',
                                metavar='groups',
                                required=True,
                                help='Add user to groups. Separate by spaces')

parser_create_group = subparsers_create.add_parser('group', help='Add new '
                                                   'group')
parser_create_group.add_argument('-G', '--Group',
                                 metavar='new_group',
                                 required=True,
                                 help='Create new ftp user group')


# delete subcommand
parser_delete = subparsers.add_parser('delete', help='delete existing user')
parser_delete.add_argument('-u', '--username',
                           metavar='username',
                           help='Delete existing user')
parser_delete.add_argument('-g', '--group',
                           metavar='groupname',
                           help='Delete existing group')

# info subcommand
parser_info = subparsers.add_parser('info', help='info about users/groups')
parser_info.add_argument('-s', '--search',
                         metavar='pattern',
                         help='Show extended info about users that match '
                              'search pattern')
parser_info.add_argument('-g', '--groups',
                         metavar='group',
                         help='Show groups to which user belongs to')
parser_info.add_argument('-G', '--group',
                         metavar='group',
                         help='Lists all users in given group')
parser_info.add_argument('-l', '--list',
                         action='store_true',
                         help='Lists all groups')


args = parser.parse_args()

if len(sys.argv) == 1:
    parser.print_help()

# create
if args.command == 'create' and len(sys.argv) == 2:
    parser_create.print_help()

if args.command == 'create':
    if args.sub_command == 'user':
        ftp = FtpUser(args.name, args.email, args.region, args.groups)
        ftp.insert_user_sql()
        ftp.insert_groups_sql()
        if email_enable:
            ftp.send_email()
    if args.sub_command == 'group':
        ftp = FtpUser('test', 'test@example.com', 'test', 'test')
        ftp.create_group(args.Group)
        sys.exit(0)

# delete
if args.command == 'delete':
    ftp = FtpUser('test', 'test@example.com', 'test', 'test')
    if args.username:
        print(ftp.delete_user(args.username))
    elif args.group:
        print(ftp.delete_group(args.group))
    else:
        parser_delete.print_help()

# info
if args.command == 'info':
    ftp = FtpUser('test', 'test@example.com', 'test', 'test')
    if args.search:
        ftp.show_user_info(args.search)
    elif args.groups:
        ftp.show_user_group(args.groups)
    elif args.group:
        ftp.show_group_users(args.group)
    elif args.list:
        for i in ftp.list_groups():
            print(i)
    else:
        parser_info.print_help()
