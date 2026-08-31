# Related projects

This guide points visitors who turn GitHub work into reader-facing updates to
useful alternatives, adjacent tools, and publishing resources.

## Possible related projects

### github-activity

- Relationship: Same-workflow project or independent implementation.
- Link: [github-activity user guide](https://github-activity.readthedocs.io/en/latest/use/)
- Why visitors may care: Collects a date-bounded repository's pull-request and
  issue activity as Markdown, which can provide the update input before this
  repository develops a longer evidence-grounded story.
- Evidence: Its official user guide describes a GitHub GraphQL library and CLI
  that render activity as Markdown changelogs or community updates.
- Confidence: likely

### GitHub Changelog Generator

- Relationship: Direct alternative or competitor.
- Link: [GitHub Changelog Generator][github-changelog-generator]
- Why visitors may care: Generates a Markdown changelog from GitHub tags,
  issues, labels, and merged pull requests when a release summary is the
  intended update rather than a daily work-log story.
- Evidence: Its official project documentation describes automated changelog
  generation from those GitHub records, with CLI and container workflows.
- Confidence: possible

### GitHub automatically generated release notes

- Relationship: Companion project, extension, or interoperability tool.
- Link: [GitHub documentation][github-generated-release-notes]
- Why visitors may care: Provides a GitHub-native release-focused update when
  a generated overview is sufficient instead of a date-owned narrative with a
  separate publisher verification boundary.
- Evidence: GitHub's documentation says generated release notes list merged
  pull requests and contributors, link to the full changelog, and support
  configurable categories.
- Confidence: possible

### MkDocs

- Relationship: Companion project, extension, or interoperability tool.
- Link: [MkDocs](https://www.mkdocs.org/)
- Why visitors may care: Builds the Markdown source that receives the daily
  publication bundle, so visitors can adapt this kind of publishing boundary
  to a static documentation site.
- Evidence: MkDocs documents a Markdown-and-YAML workflow that builds static
  HTML; this repository's local daily publisher imports approved posts into a
  sibling MkDocs site.
- Confidence: likely

### Keep a Changelog

- Relationship: Domain standard, guide, dataset, or other visitor resource.
- Link: [Keep a Changelog](https://keepachangelog.com/en/2.0.0/)
- Why visitors may care: Gives makers a human-oriented way to select notable
  changes before turning that work into a broader update for readers.
- Evidence: The guide defines a changelog as a curated chronological list of
  notable changes and states that changelogs are for humans rather than
  machines.
- Confidence: possible

## Evidence notes

Two bounded discovery rounds used the repository's GitHub-evidence,
reader-facing daily-publication, Markdown, and static-site vocabulary. The
entries above rely on official project documentation, GitHub documentation, and
the Keep a Changelog guide. Each shares a visitor audience of makers who need
to collect, curate, publish, or compare updates about software work. No source
found an explicit lineage, reciprocal link, or full end-to-end alternative, so
the entries remain in the possible tier except for github-activity and MkDocs,
whose official documentation establishes a substantially overlapping workflow.

[github-changelog-generator]:
  https://github.com/github-changelog-generator/github-changelog-generator
[github-generated-release-notes]:
  https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
