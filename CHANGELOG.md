# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v1.3.0] - 2026-03-02
### Added
- Discovery mode: leave `identifier` and `target_group_arn` empty to auto-discover RDS resources via `place_into_target_group` tag
- Configurable Lambda timeout via `lambda_timeout` variable (default: 60s)
- Validation precondition ensuring `identifier` and `target_group_arn` are both set or both empty
- Paginated API calls for discovery mode to handle large numbers of RDS resources
- Per-target-group error handling in discovery mode

### Changed
- `identifier` and `target_group_arn` are now optional (default to empty string)
- Lambda timeout increased from default 3s to 60s
- Refactored `handle_single_instance` to accept instance info dict instead of identifier
- Refactored `handle_aurora_cluster` to accept optional pre-fetched instances list
- Extracted target group sync logic into reusable `sync_target_group` function

## [v1.2.0] - 2026-01-30
### Changed
- Allow RDS instances in 'backing-up' and 'modifying' states to be processed

## [v1.1.0] - 2025-06-25
### Added
- suport for a single RDS instance
### Fixed
- constant tags, moved to var

## [v1.0.0] - 2025-06-24
- initial release
