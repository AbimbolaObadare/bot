# Changelog

## 2.9.2 (2021-10-06)

#### Fixes

* other incompatibilities in the latest IG version

Full set of changes: [`2.9.1...2.9.2`](https://github.com/GramAddict/bot/compare/2.9.1...2.9.2)

## 2.9.1 (2021-10-06)

#### New Features

* module version thanks to @patbengr
#### Fixes

* compatibility with IG: 208.0.0.32.135

Full set of changes: [`2.9.0...2.9.1`](https://github.com/GramAddict/bot/compare/2.9.0...2.9.1)

## 2.9.0 (2021-08-25)

#### New Features

* new argument to control how many skips in jobs with posts (e.g.: hashtag-post-top) are allowed before moving to another source / job
* new job to unfollow people who are following you
* new filter for skipping accounts with banned biography language
#### Performance improvements

* improved readability of the code and correct some typos
* moving sibling folders of run.py will no longer executed automatically

Full set of changes: [`2.8.0...2.9.0`](https://github.com/GramAddict/bot/compare/2.8.0...2.9.0)

## 2.8.0 (2021-08-04)

#### New Features

* new filters: 'skip_if_link_in_bio: true/false' and 'mutual_friends: a_number' min count
* new feature added: pre and post script execution

Full set of changes: [`2.7.7...2.8.0`](https://github.com/GramAddict/bot/compare/2.7.7...2.8.0)

## 2.7.7 (2021-08-03)

#### Fixes

* place first post not found [#208](https://github.com/GramAddict/bot/issues/208)
* replace detect-block with disable-block-detection
#### Performance improvements

* removed unneeded class and sort imports

Full set of changes: [`2.7.6...2.7.7`](https://github.com/GramAddict/bot/compare/2.7.6...2.7.7)

## 2.7.6 (2021-07-31)

#### Fixes

* missing resource id for sorting following list

Full set of changes: [`2.7.5...2.7.6`](https://github.com/GramAddict/bot/compare/2.7.5...2.7.6)

## 2.7.5 (2021-07-30)

#### New Features

* new argument "detect_block: true/false" to enable/ disable block check after every action
#### Fixes

* a better way to sort following list [#207](https://github.com/GramAddict/bot/issues/207)
#### Performance improvements

* add debug info for swipes
#### Refactorings

* sort imports

Full set of changes: [`2.7.4...2.7.5`](https://github.com/GramAddict/bot/compare/2.7.4...2.7.5)

## 2.7.4 (2021-07-25)

#### Fixes

* support for Ig v. 197.0.0.26.119

Full set of changes: [`2.7.3...2.7.4`](https://github.com/GramAddict/bot/compare/2.7.3...2.7.4)

## 2.7.3 (2021-07-14)

#### Fixes

* sometimes the bot press on 'Switch IME' instead of open your profile
* automatic change in English locale stopped working

Full set of changes: [`2.7.2...2.7.3`](https://github.com/GramAddict/bot/compare/2.7.2...2.7.3)

## 2.7.2 (2021-07-14)

#### Fixes

* bug in open post container when someone in your 'following list' has also liked the post
#### Performance improvements

* lowered a little bit the swipe up in sorting `Following accounts`

Full set of changes: [`2.7.1...2.7.2`](https://github.com/GramAddict/bot/compare/2.7.1...2.7.2)

## 2.7.1 (2021-07-13)

#### New Features

* you can dump your current screen with that command `gramaddict dump`
#### Performance improvements

* we don't need to click on a obj if we are already on it

Full set of changes: [`2.7.0...2.7.1`](https://github.com/GramAddict/bot/compare/2.7.0...2.7.1)

## 2.7.0 (2021-07-12)

#### New Features

* you can use spintax for comments and PM from now
#### Fixes

* forgot to remove 'time_left' when calling print_telegram_reports at the end of all sessions
* in config-examples forgot 'comment_blogger' and fix typo in 'comment_blogger_following'

Full set of changes: [`2.6.5...2.7.0`](https://github.com/GramAddict/bot/compare/2.6.5...2.7.0)

## 2.6.5 (2021-07-06)

#### Fixes

* the count of items in the carousels stopped at the first match
* from now on, every type of interaction is counted as successful and not just likes

Full set of changes: [`2.6.4...2.6.5`](https://github.com/GramAddict/bot/compare/2.6.4...2.6.5)

## 2.6.4 (2021-07-01)

#### Fixes

* telegram-reports when out of working hours crashed
#### Performance improvements

* improve update checking
#### Docs

* text improvement and typo corrections

Full set of changes: [`2.6.3...2.6.4`](https://github.com/GramAddict/bot/compare/2.6.3...2.6.4)

## 2.6.3 (2021-06-26)

#### Fixes

* time left in telegram-reports was wrong

Full set of changes: [`2.6.2...2.6.3`](https://github.com/GramAddict/bot/compare/2.6.2...2.6.3)

## 2.6.2 (2021-06-25)

#### Fixes

* there was a problem with likers list
* there was a problem with the way I moved the reports at the end of sessions
#### Performance improvements

* the bot can recognize hashtag suggestions in feed
* telegram-reports improved
#### Docs

* typo in readme

Full set of changes: [`2.6.1...2.6.2`](https://github.com/GramAddict/bot/compare/2.6.1...2.6.2)

## 2.6.1 (2021-06-24)

#### Performance improvements

* we can use an entry point from now
#### Docs

* correct a typo in telegram-reports
* improved the README

Full set of changes: [`2.6.0...2.6.1`](https://github.com/GramAddict/bot/compare/2.6.0...2.6.1)

## 2.6.0 (2021-06-24)

#### New Features

* you can run GramAddict from the command line for initializing your account folder with all the files needed
* add support for allow re-interaction after a given amount of hours
#### Fixes

* too many `filters.yml is not loaded`
* telegram-reports typo in report
* add support for viewers count where likes count is missing
* browse the carousel could fail in some circumstances
#### Docs

* complitely rewrote the README.md
#### Others

* donation alert when bot stops by pressing CTRL+C
