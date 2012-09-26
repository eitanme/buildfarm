Documenting a stack using the "doc" script, architecture and usage
-----------------------------------------------------

Overview
=====================================================

The ``doc`` script wraps the ``rosdoc_lite`` tool to provide stack-level API documentation. Running this script generates html documentation for each stack along with a set of doxygen "tag" files used for cross-referencing support. The script automatically pulls from the ``rosdoc_tag_index`` repository to find the list of available tag files for a given distribution and updates this same repository at the end of a documentation run. The script also uses ``rsync`` to push the generated documentation and tag files to Willow Garage's servers.
