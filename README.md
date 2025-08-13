aws_key_rotate
==============

This script makes it easy to rotate your AWS access keys, and store a new version in your ~/.aws/credentials file.

When you run it, it will look at the profiles in that file, and prompt you to choose one of them.
It will then use those credentials to connect to your account, show you what keys you have, give you the option to create a new one (or delete one if you've hit the limit of two), and replace the details in the credentials file, making a backup as it goes.

Claude wrote a fair bit of this and I fixed the bugs!

Use at your own risk.


Quentin Stafford-Fraser
August 2025

