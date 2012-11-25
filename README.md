Lettuce-Farmer
==============
A Sublime Text 2 plugin that provides syntax highlighting, step completion, and
[SublimeLinter](https://github.com/SublimeLinter/SublimeLinter) style step
validation for writing [Lettuce](http://lettuce.it) feature files.

The intention of this plugin is to ease the use of Lettuce for BDD and hopefully
make it simple enough for non-engineers to write feature files. At least that's
the hope.


Installation
============
**IMPORTANT:** Once Lettuce-Farmer is installed you must enable the
auto-completion for feature files in your preferences. For most people this
will be in the default settings 'Settings - Default' (`Preferences > Settings -
Default`), but if you have the 'auto_complete_selector' defined in another file
you will need to change this there.

    // Controls what scopes auto complete will be triggered in
    "auto_complete_selector": "source - comment, text.lettuce.feature",

Your list may not look the same, but the critical part is that
'text.lettuce.feature' is present.

Using Package Control:
----------------------
**SUBMITTED BUT NOT YET PULLED INTO PACKAGE CONTROL**

[Package Control](http://wbond.net/sublime_packages/package_control) is by far
the easiest way to install Lettuce-Farmer. Once you have Package Control
installed and SublimeText2 restarted, select Package Control (`Preferences >
Package Control`) and then 'Install Package'. Once they package list comes up
you can browse for or type 'Lettuce-Farmer'.

Using Git:
----------
Clone the Lettuce-Farmer repository in your Packages directory. You can find
where the directory via `Preferences > Browse Packages...`

    git clone https://github.com/kylederkacz/lettuce-farmer.git

Manual:
-------
[Download](https://github.com/kylederkacz/lettuce-farmer/archive/master.zip) the
plugin from Git and extract the contents into a folder in your Packages
directory.

To open your packages directory goto `Preferences > Browse Packages...`

Platform Support
================

Currently, only *Mac OSX* is officially supported. 

*Windows* has an [issue](https://github.com/kylederkacz/lettuce-farmer/issues/1)
when loading the lettuce library due to a missing unicode library that isn't
in the version of python that ships with the Windows version of Sublime. The
portable version has not been tested at all.

*Linux* may work, but has not yet been tested.

Shout Outs
==========
The Lettuce Farmer syntax highlighting is primarily based on npverni's
[cucumber-sublime2-bundle](https://github.com/npverni/cucumber-sublime2-bundle).