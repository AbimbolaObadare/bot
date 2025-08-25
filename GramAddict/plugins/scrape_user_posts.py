import logging
import os
from functools import partial
from random import seed
from typing import Set, Dict, List

from colorama import Style

from GramAddict.core.decorators import run_safely
from GramAddict.core.device_facade import DeviceFacade, Timeout, Direction
from GramAddict.core.navigation import nav_to_blogger
from GramAddict.core.plugin_loader import Plugin
from GramAddict.core.resources import ResourceID as resources
from GramAddict.core.resources import ClassName
from GramAddict.core.utils import get_value, random_sleep, inspect_current_view
from GramAddict.core.views import PostsViewList, OpenedPostView, PostsGridView, ProfileView, SwipeTo

logger = logging.getLogger(__name__)

# Script Initialization
seed()


class ScrapeLikersAndCommenters(Plugin):
    """Scrapes likers and commenters from specified users' posts"""

    def __init__(self):
        super().__init__()
        self.description = "Scrapes likers and commenters from specified users' posts"
        self.arguments = [
            {
                "arg": "--scrape-likers-commenters",
                "nargs": "+",
                "help": "list of usernames whose post likers and commenters you want to scrape",
                "metavar": ("username1", "username2"),
                "default": None,
                "operation": True,
            },
            {
                "arg": "--scrape-posts-count",
                "nargs": None,
                "help": "number of posts to scrape from each user (e.g. 5 or 5-10)",
                "metavar": "5-10",
                "default": "5",
            },
        ]

    def run(self, device, configs, storage, sessions, profile_filter, plugin):
        class State:
            def __init__(self):
                pass

            is_job_completed = False

        self.device_id = configs.args.device
        self.sessions = sessions
        self.session_state = sessions[-1]
        self.args = configs.args
        self.current_mode = plugin
        self.ResourceID = resources(self.args.app_id)

        # Handle sources
        sources = [s for s in self.args.scrape_likers_commenters if s.strip()]

        for source in sources:
            self.state = State()
            source = source.strip()
            if source.startswith("@"):
                source = source[1:]

            logger.info(f"Scraping likers and commenters from @{source}", extra={"color": f"{Style.BRIGHT}"})

            @run_safely(
                device=device,
                device_id=self.device_id,
                sessions=self.sessions,
                session_state=self.session_state,
                screen_record=self.args.screen_record,
                configs=configs,
            )
            def job():
                self.scrape_user_posts(device, source, storage)
                self.state.is_job_completed = True

            while not self.state.is_job_completed:
                job()

    def scrape_user_posts(self, device, username, storage):
        """Navigate to user and scrape their posts"""

        # Navigate to the user's profile
        if not nav_to_blogger(device, username, self.session_state.my_username):
            logger.error(f"Could not navigate to @{username}")
            return

        # Check if profile is accessible
        profile_view = ProfileView(device)
        is_private = profile_view.isPrivateAccount()
        posts_count = profile_view.getPostsCount()

        if is_private:
            logger.warning(f"@{username} has a private account. Cannot scrape.")
            return

        if posts_count == 0:
            logger.warning(f"@{username} has no posts.")
            return

        # Scroll to posts area
        swipe_result = profile_view.swipe_to_fit_posts()
        if swipe_result == -1:
            logger.warning(f"Could not access posts for @{username}")
            return

        # Determine how many posts to scrape
        posts_to_scrape = get_value(self.args.scrape_posts_count, "Posts to scrape: {}", 5)
        posts_to_scrape = min(posts_to_scrape, posts_count)

        logger.info(f"Will scrape {posts_to_scrape} posts from @{username}")

        # Storage for scraped data
        all_likers: Set[str] = set()
        all_commenters: Set[str] = set()
        posts_data: List[Dict] = []

        # Navigate through posts
        posts_grid = PostsGridView(device)
        posts_scraped = 0

        for row in range(5):  # Max 5 rows to avoid scrolling issues
            for col in range(3):
                if posts_scraped >= posts_to_scrape:
                    break

                post_num = posts_scraped + 1
                logger.info(f"Opening post #{post_num}")

                try:
                    # Open the post
                    opened_post, media_type, _ = posts_grid.navigateToPost(row, col)

                    if opened_post is None:
                        logger.warning(f"Could not open post at position ({row}, {col})")
                        continue

                    # Scrape likers and commenters for this post
                    post_likers, post_commenters = self.scrape_post_engagement(device, post_num, username)

                    # Store data
                    all_likers.update(post_likers)
                    all_commenters.update(post_commenters)
                    posts_data.append({
                        "post_number": post_num, 
                        "likers": post_likers, 
                        "commenters": post_commenters
                    })

                    posts_scraped += 1

                except Exception as e:
                    logger.error(f"Error processing post #{post_num}: {e}")

                finally:
                    # Always try to go back to profile
                    device.back()
                    random_sleep()

            if posts_scraped >= posts_to_scrape:
                break

            # Scroll down to load more posts if needed
            if posts_scraped < posts_to_scrape and row < 4:
                try:
                    posts_grid.scrollDown()
                    random_sleep()
                except:
                    logger.debug("Could not scroll down for more posts")
                    break

        # Save the scraped data
        self.save_scraped_data(username, all_likers, all_commenters, posts_data, storage)

        logger.info(f"Finished scraping @{username}. "
                   f"Total unique likers: {len(all_likers)}, "
                   f"Total unique commenters: {len(all_commenters)}")

    def scrape_post_engagement(self, device, post_num, username):
        """Scrape likers and commenters from an opened post"""

        likers = set()
        commenters = set()

        try:
            # First, scrape likers
            logger.info(f"Scraping likers for post #{post_num}")
            likers = self.scrape_likers(device)

            # Then, scrape commenters
            logger.info(f"Scraping commenters for post #{post_num}")
            commenters = self.scrape_commenters(device)

            logger.info(f"Post #{post_num}: Found {len(likers)} likers, {len(commenters)} commenters")

        except Exception as e:
            logger.error(f"Error scraping post #{post_num}: {e}")

        return likers, commenters

    def scrape_likers(self, device):
        """Scrape likers from the current post"""
        likers = set()

        try:
            # Find and open likers container
            posts_view = PostsViewList(device)
            has_likers, num_likers = posts_view._find_likers_container()

            if not has_likers or num_likers == 0:
                logger.debug("No likers found or cannot access likers")
                return likers

            # Open likers list
            posts_view.open_likers_container()
            random_sleep()

            # Get the list view
            opened_post = OpenedPostView(device)
            likes_list_view = opened_post._getListViewLikers()

            if likes_list_view is None:
                logger.warning("Could not open likers list")
                device.back()
                return likers

            # Iterate through likers
            max_scrolls = 5  # Reduced to avoid too much scrolling
            scroll_count = 0
            prev_likers_count = 0

            while scroll_count < max_scrolls:
                user_container = opened_post._getUserContainer()

                if user_container is None:
                    break

                try:
                    row_height, n_users = inspect_current_view(user_container)

                    for item in user_container:
                        if item.get_height() < row_height:
                            continue

                        username_view = opened_post._getUserName(item)
                        if username_view.exists(Timeout.SHORT):
                            liker_username = username_view.get_text()
                            if liker_username and liker_username.strip():
                                likers.add(liker_username.strip())

                except Exception as e:
                    logger.debug(f"Error iterating likers: {e}")
                    break

                # Check if we got new likers
                current_count = len(likers)
                if current_count == prev_likers_count:
                    logger.debug("No new likers found, stopping scroll")
                    break

                prev_likers_count = current_count
                likes_list_view.scroll(Direction.DOWN)
                scroll_count += 1
                random_sleep(1, 2, modulable=False)

            # Go back to post
            device.back()
            random_sleep()

        except Exception as e:
            logger.error(f"Error scraping likers: {e}")
            # Make sure we go back
            device.back()

        return likers

    def scrape_commenters(self, device):
        """Scrape commenters from the current post"""
        commenters = set()

        try:
            # Find and click comment button
            comment_button = device.find(resourceId=self.ResourceID.ROW_FEED_BUTTON_COMMENT)

            if not comment_button.exists(Timeout.SHORT):
                logger.debug("Cannot find comment button")
                return commenters

            comment_button.click()
            random_sleep()

            # Check if comments are available
            comments_list = device.find(resourceId=self.ResourceID.LIST, className=ClassName.LIST_VIEW)

            if not comments_list.exists(Timeout.MEDIUM):
                logger.debug("Comments not available or disabled")
                device.back()
                return commenters

            # Try to find comment usernames using different selectors
            max_scrolls = 3  # Reduced scrolling for comments
            scroll_count = 0
            prev_commenters_count = 0

            while scroll_count < max_scrolls:
                # Look for username elements in comments
                # Instagram comment usernames are usually in separate elements
                username_elements = device.find(
                    resourceId=self.ResourceID.ROW_USER_PRIMARY_NAME,
                    className=ClassName.TEXT_VIEW
                )

                if username_elements.exists():
                    try:
                        for i in range(min(10, username_elements.count_items())):  # Limit to avoid infinite loops
                            username_elem = username_elements.child(index=i)
                            if username_elem.exists():
                                commenter_username = username_elem.get_text()
                                if commenter_username and commenter_username.strip():
                                    commenters.add(commenter_username.strip())
                    except Exception as e:
                        logger.debug(f"Error extracting commenter usernames: {e}")

                # Alternative: Look for comment container elements
                comment_containers = device.find(resourceId=self.ResourceID.ROW_COMMENT_TEXTVIEW_COMMENT)
                if comment_containers.exists():
                    try:
                        # Try to find sibling username elements
                        for i in range(min(5, comment_containers.count_items())):
                            comment_container = comment_containers.child(index=i)
                            # Look for username in the parent container
                            parent = comment_container.sibling(
                                resourceId=self.ResourceID.ROW_USER_PRIMARY_NAME
                            )
                            if parent.exists():
                                username_text = parent.get_text()
                                if username_text and username_text.strip():
                                    commenters.add(username_text.strip())
                    except Exception as e:
                        logger.debug(f"Error extracting from comment containers: {e}")

                # Check if we got new commenters
                current_count = len(commenters)
                if current_count == prev_commenters_count:
                    logger.debug("No new commenters found, stopping scroll")
                    break

                prev_commenters_count = current_count
                comments_list.scroll(Direction.DOWN)
                scroll_count += 1
                random_sleep(1, 2, modulable=False)

            # Go back to post
            device.back()
            random_sleep()

        except Exception as e:
            logger.error(f"Error scraping commenters: {e}")
            # Make sure we go back
            device.back()

        return commenters

    def save_scraped_data(self, username, likers, commenters, posts_data, storage):
        """Save the scraped data to a file"""

        # Prepare filename
        filename = f"{username}_likers_commenters.txt"
        filepath = os.path.join(storage.account_path, filename)

        # Prepare the data
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"=== Scraped Data for @{username} ===\n")
            f.write(f"Total posts scraped: {len(posts_data)}\n")
            f.write(f"Total unique likers: {len(likers)}\n")
            f.write(f"Total unique commenters: {len(commenters)}\n")
            f.write(f"{'='*50}\n\n")

            # Users who are both likers and commenters
            both = likers.intersection(commenters)
            only_likers = likers - commenters
            only_commenters = commenters - likers

            f.write(f"=== Summary ===\n")
            f.write(f"Users who both liked and commented: {len(both)}\n")
            f.write(f"Users who only liked: {len(only_likers)}\n")
            f.write(f"Users who only commented: {len(only_commenters)}\n\n")

            # Write detailed user list
            f.write(f"=== All Users (with type) ===\n")
            all_users = set()

            for user in sorted(both):
                f.write(f"{user} [LIKER+COMMENTER]\n")
                all_users.add(user)

            for user in sorted(only_likers):
                f.write(f"{user} [LIKER]\n")
                all_users.add(user)

            for user in sorted(only_commenters):
                f.write(f"{user} [COMMENTER]\n")
                all_users.add(user)

            # Write post-by-post breakdown
            f.write(f"\n{'='*50}\n")
            f.write(f"=== Post-by-Post Breakdown ===\n")

            for post in posts_data:
                f.write(f"\nPost #{post['post_number']}:\n")
                f.write(f"  Likers ({len(post['likers'])}): {', '.join(sorted(post['likers'])) if post['likers'] else 'None'}\n")
                f.write(f"  Commenters ({len(post['commenters'])}): {', '.join(sorted(post['commenters'])) if post['commenters'] else 'None'}\n")

        logger.info(f"Saved scraped data to {filepath}")

        # Also create a simple list file with just usernames
        simple_filename = f"{username}_all_users.txt"
        simple_filepath = os.path.join(storage.account_path, simple_filename)

        with open(simple_filepath, "w", encoding="utf-8") as f:
            for user in sorted(all_users):
                f.write(f"{user}\n")

        logger.info(f"Saved simple user list to {simple_filepath}")