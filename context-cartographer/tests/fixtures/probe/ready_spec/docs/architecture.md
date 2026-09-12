# Architecture

The planner is one process with three modules: the catalogue reader, the print
renderer and a thin command line entry point. The catalogue is a text file so a
volunteer can edit it with any editor and review the change in a diff.

There is no database and no network client in the first release.
