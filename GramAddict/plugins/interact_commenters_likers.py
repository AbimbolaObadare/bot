import logging
from functools import partial
from random import seed, choice

from colorama import Style, Fore

from GramAddict.core.decorators import run_safely
from GramAddict.core.device_facade import DeviceFacade, Direction, Timeout
from GramAddict.core.interaction import (
    interact_with_user,
    is_follow_limit_reached_for_source,
)
from GramAddict.core.navigation import nav_to_blogger
from GramAddict.core.plugin_loader import Plugin
from GramAddict.core.resources import ClassName, ResourceID as resources
from GramAddict.core.scroll_end_detector import ScrollEndDetector
from GramAddict.core.storage import FollowingStatus
from GramAddict.core.utils import (
    get_value,
    init_on_things,
    inspect_current_view,
    random_sleep,
    sample_sources,
)
from GramAddict.core.views import (
    OpenedPostView,
    PostsGridView,
    ProfileView,
    UniversalActions,
)

logger = logging.getLogger(__name__)

# Script Initialization
seed()


class InteractCommentersAndLikers(Plugin):
    """Handles the functionality of interacting with commenters and likers of posts from specified usernames"""

    def __init__(self):
        super().__init__()
        self.description = "Handles the functionality of interacting with commenters and likers of posts from specified usernames"
        self.arguments = [
            {
                "arg": "--commenters-likers",
                "nargs": "+",
                "help": "list of usernames whose post commenters and likers you want to interact with",
                "metavar": ("username1", "username2"),
                "default": None,
                "operation": True,
            },
            {
                "arg": "--commenters-likers-posts-count",
                "nargs": None,
                "help": "number of recent posts to check for each user",
                "metavar": "3",
                "default": "3",
            },
            {
                "arg": "--commenters-percentage",
                "nargs": None,
                "help": "percentage of commenters to interact with vs likers",
                "metavar": "50",
                "default": "50",
            },
            {
                "arg": "--max-commenters-per-post",
                "nargs": None,
                "help": "maximum number of commenters to interact with per post",
                "metavar": "5",
                "default": "5",
            },
            {
                "arg": "--max-likers-per-post",
                "nargs": None,
                "help": "maximum number of likers to interact with per post",
                "metavar": "10",
                "default": "10",
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
        self.ResourceID = resources(self.args.app_id)
        self.current_mode = plugin

        # Handle sources
        sources = [s for s in self.args.commenters_likers if s.strip()]
        
        for source in sample_sources(sources, self.args.truncate_sources):
            (
                active_limits_reached,
                _,
                actions_limit_reached,
            ) = self.session_state.check_limit(limit_type=self.session_state.Limit.ALL)
            limit_reached = active_limits_reached or actions_limit_reached

            self.state = State()
            logger.info(f"Handle {source}", extra={"color": f"{Style.BRIGHT}"})

            # Init common things
            (
                on_interaction,
                stories_percentage,
                likes_percentage,
                follow_percentage,
                comment_percentage,
                pm_percentage,
                _,
            ) = init_on_things(source, self.args, self.sessions, self.session_state)

            @run_safely(
                device=device,
                device_id=self.device_id,
                sessions=self.sessions,
                session_state=self.session_state,
                screen_record=self.args.screen_record,
                configs=configs,
            )
            def job():
                self.handle_commenters_and_likers(
                    device,
                    source,
                    plugin,
                    storage,
                    profile_filter,
                    on_interaction,
                    stories_percentage,
                    likes_percentage,
                    follow_percentage,
                    comment_percentage,
                    pm_percentage,
                )
                self.state.is_job_completed = True

            while not self.state.is_job_completed and not limit_reached:
                job()

            if limit_reached:
                logger.info("Ending session.")
                self.session_state.check_limit(
                    limit_type=self.session_state.Limit.ALL, output=True
                )
                break

    def handle_commenters_and_likers(
        self,
        device,
        username,
        current_job,
        storage,
        profile_filter,
        on_interaction,
        stories_percentage,
        likes_percentage,
        follow_percentage,
        comment_percentage,
        pm_percentage,
    ):
        interaction = partial(
            interact_with_user,
            my_username=self.session_state.my_username,
            likes_count=self.args.likes_count,
            likes_percentage=likes_percentage,
            stories_percentage=stories_percentage,
            follow_percentage=follow_percentage,
            comment_percentage=comment_percentage,
            pm_percentage=pm_percentage,
            profile_filter=profile_filter,
            args=self.args,
            session_state=self.session_state,
            scraping_file=self.args.scrape_to_file,
            current_mode=self.current_mode,
        )
        
        source_follow_limit = (
            get_value(self.args.follow_limit, None, 15)
            if self.args.follow_limit is not None
            else None
        )
        is_follow_limit_reached = partial(
            is_follow_limit_reached_for_source,
            session_state=self.session_state,
            follow_limit=source_follow_limit,
            source=username,
        )

        # Navigate to user profile
        if not nav_to_blogger(device, username, current_job):
            logger.error(f"Could not navigate to @{username}")
            return

        profile_view = ProfileView(device)
        posts_count = profile_view.getPostsCount()
        
        if posts_count == 0:
            logger.info(f"@{username} has no posts to check")
            return

        # Get number of posts to check
        try:
            posts_to_check = get_value(self.args.commenters_likers_posts_count, None, 3)
            if isinstance(posts_to_check, str):
                posts_to_check = int(posts_to_check)
            elif posts_to_check is None:
                posts_to_check = 3
            posts_to_check = min(posts_to_check, posts_count)
        except Exception as e:
            logger.debug(f"Error processing posts_to_check: {e}, defaulting to 3")
            posts_to_check = min(3, posts_count)
        
        logger.info(f"Checking {posts_to_check} recent posts from @{username}")
        
        # Swipe to see posts grid
        profile_view.swipe_to_fit_posts()
        posts_grid_view = PostsGridView(device)

        # Iterate through recent posts
        for post_index in range(posts_to_check):
            row = post_index // 3
            col = post_index % 3
            
            logger.info(f"Opening post #{post_index + 1} of @{username}")
            
            opened_post_view, media_type, obj_count = posts_grid_view.navigateToPost(row, col)
            
            if opened_post_view is None:
                logger.warning(f"Could not open post #{post_index + 1}")
                continue

            # Decide whether to check commenters or likers based on percentage
            try:
                commenters_percentage = get_value(self.args.commenters_percentage, None, 50)
                if isinstance(commenters_percentage, str):
                    commenters_percentage = int(commenters_percentage)
                elif commenters_percentage is None:
                    commenters_percentage = 50
                
                # Use random choice for 50/50, otherwise use percentage logic
                import random
                check_commenters = random.randint(1, 100) <= commenters_percentage
                
            except Exception as e:
                logger.debug(f"Error processing commenters_percentage: {e}, defaulting to 50/50")
                check_commenters = choice([True, False])

            if check_commenters:
                logger.info("Checking commenters for this post")
                self._interact_with_commenters(
                    device, 
                    storage, 
                    interaction, 
                    is_follow_limit_reached, 
                    on_interaction, 
                    username
                )
            else:
                logger.info("Checking likers for this post")
                self._interact_with_likers(
                    device, 
                    storage, 
                    interaction, 
                    is_follow_limit_reached, 
                    on_interaction, 
                    username
                )

            # Go back to profile
            device.back()
            random_sleep(2, 4, modulable=False)

        # Return to main profile
        device.back()

    def _interact_with_commenters(self, device, storage, interaction, is_follow_limit_reached, on_interaction, target_username):
        """Interact with commenters of the current post"""
        try:
            max_commenters = get_value(self.args.max_commenters_per_post, None, 5)
            if isinstance(max_commenters, str):
                max_commenters = int(max_commenters)
            elif max_commenters is None:
                max_commenters = 5
        except Exception as e:
            logger.debug(f"Error processing max_commenters_per_post: {e}, defaulting to 5")
            max_commenters = 5
        
        # Look for comment button
        comment_button = device.find(
            resourceId=self.ResourceID.ROW_FEED_BUTTON_COMMENT,
        )
        
        if not comment_button.exists(Timeout.MEDIUM):
            logger.warning("Could not find comment button on this post")
            return

        comment_button.click()
        random_sleep(2, 3, modulable=False)

        # Check if comments are available
        comments_list = device.find(resourceId=self.ResourceID.LIST)
        if not comments_list.exists(Timeout.MEDIUM):
            logger.warning("Comments are disabled or not loading for this post")
            device.back()
            return

        interacted_commenters = 0
        processed_commenters = set()

        skipped_list_limit = get_value(self.args.skipped_list_limit, None, 15)
        scroll_end_detector = ScrollEndDetector(
            repeats_to_end=2,
            skipped_list_limit=skipped_list_limit,
            skipped_fling_limit=0,
        )

        while interacted_commenters < max_commenters:
            try:
                scroll_end_detector.notify_new_page()
                
                # Find comment containers
                comment_containers = device.find(
                    resourceIdMatches=self.ResourceID.ROW_COMMENT_TEXTVIEW_COMMENT
                )
                
                if not comment_containers.exists():
                    logger.info("No more comments found")
                    break

                # Get visible comments
                for comment_container in comment_containers:
                    if interacted_commenters >= max_commenters:
                        break
                
                    # Try to find username in comment
                    try:
                        # Look for the username that made the comment
                        parent_container = comment_container.up()
                        username_views = parent_container.child(
                            className=ClassName.TEXT_VIEW
                        )
                        
                        commenter_username = None
                        # Try different ways to find the username
                        for view in username_views:
                            text = view.get_text(error=False)
                            if text and not text.startswith('#') and len(text) > 0:
                                # This might be the username
                                commenter_username = text.strip()
                                break
                        
                        if not commenter_username:
                            # Try alternative method
                            username_view = comment_container.sibling(
                                className=ClassName.TEXT_VIEW
                            )
                            if username_view.exists():
                                commenter_username = username_view.get_text(error=False)
                        
                        if not commenter_username:
                            continue
                        
                        if commenter_username in processed_commenters:
                            continue
                        
                        processed_commenters.add(commenter_username)
                        scroll_end_detector.notify_username_iterated(commenter_username)

                        # Check if we should interact with this commenter
                        if storage.is_user_in_blacklist(commenter_username):
                            logger.info(f"@{commenter_username} is in blacklist. Skip.")
                            continue

                        interacted, interacted_when = storage.check_user_was_interacted(commenter_username)
                        if interacted:
                            can_reinteract = storage.can_be_reinteract(
                                interacted_when,
                                get_value(self.args.can_reinteract_after, None, 0),
                            )
                            if not can_reinteract:
                                logger.info(f"@{commenter_username}: already interacted recently. Skip.")
                                continue

                        # Click on commenter username to go to profile
                        logger.info(f"@{commenter_username}: interact", extra={"color": f"{Fore.YELLOW}"})
                        
                        # Try to click on the username area
                        clicked = False
                        try:
                            # Try clicking on the comment container area
                            parent_container = comment_container.up()
                            if parent_container.click_retry():
                                clicked = True
                        except:
                            # Fallback: try clicking on comment container directly
                            if comment_container.click_retry():
                                clicked = True
                        
                        if clicked:
                            # Perform interaction
                            success = self._perform_interaction(
                                device, 
                                storage, 
                                interaction, 
                                is_follow_limit_reached, 
                                commenter_username, 
                                target_username
                            )
                            
                            if success:
                                interacted_commenters += 1
                                on_interaction(succeed=True, followed=False, scraped=False)
                            
                            # Go back to comments
                            device.back()
                            random_sleep(1, 2, modulable=False)

                    except Exception as e:
                        logger.debug(f"Error processing commenter: {e}")
                        continue

                # Check if we've reached the end or should scroll
                if scroll_end_detector.is_the_end():
                    break
                
                # Scroll down to see more comments
                try:
                    comments_list.scroll(Direction.DOWN)
                    random_sleep(1, 2, modulable=False)
                except Exception as e:
                    logger.debug(f"Error scrolling comments: {e}")
                    break
                    
            except Exception as e:
                logger.debug(f"Error in commenters loop: {e}")
                break

        logger.info(f"Interacted with {interacted_commenters} commenters")
        device.back()  # Go back from comments

    def _interact_with_likers(self, device, storage, interaction, is_follow_limit_reached, on_interaction, target_username):
        """Interact with likers of the current post"""
        try:
            max_likers = get_value(self.args.max_likers_per_post, None, 10)
            if isinstance(max_likers, str):
                max_likers = int(max_likers)
            elif max_likers is None:
                max_likers = 10
        except Exception as e:
            logger.debug(f"Error processing max_likers_per_post: {e}, defaulting to 10")
            max_likers = 10
        
        # Look for likes section
        likes_view = device.find(
            resourceId=self.ResourceID.ROW_FEED_TEXTVIEW_LIKES,
            className=ClassName.TEXT_VIEW,
        )
        
        if not likes_view.exists(Timeout.MEDIUM):
            logger.warning("Could not find likes section on this post")
            return

        # Click on likes to open likers list
        likes_view.click()
        random_sleep(2, 3, modulable=False)

        # Check if likers list is available
        likers_list = device.find(resourceId=self.ResourceID.LIST)
        if not likers_list.exists(Timeout.MEDIUM):
            logger.warning("Likers list not available for this post")
            device.back()
            return

        interacted_likers = 0
        processed_likers = set()

        skipped_list_limit = get_value(self.args.skipped_list_limit, None, 15)
        scroll_end_detector = ScrollEndDetector(
            repeats_to_end=2,
            skipped_list_limit=skipped_list_limit,
            skipped_fling_limit=0,
        )

        while interacted_likers < max_likers:
            try:
                scroll_end_detector.notify_new_page()
                
                # Find user containers in likers list
                user_containers = device.find(
                    resourceIdMatches=self.ResourceID.USER_LIST_CONTAINER,
                )
                
                if not user_containers.exists():
                    logger.info("No more likers found")
                    break

                try:
                    row_height, n_users = inspect_current_view(user_containers)
                except Exception:
                    logger.warning("Could not inspect likers view")
                    break

                # Get visible likers
                for user_container in user_containers:
                    if interacted_likers >= max_likers:
                        break
                
                    try:
                        cur_row_height = user_container.get_height()
                        if cur_row_height < row_height:
                            continue
                        
                        username_view = user_container.child(
                            resourceId=self.ResourceID.ROW_USER_PRIMARY_NAME,
                        )
                        
                        if not username_view.exists():
                            continue
                        
                        liker_username = username_view.get_text()
                        
                        if liker_username in processed_likers:
                            continue
                        
                        processed_likers.add(liker_username)
                        scroll_end_detector.notify_username_iterated(liker_username)

                        # Check if we should interact with this liker
                        if storage.is_user_in_blacklist(liker_username):
                            logger.info(f"@{liker_username} is in blacklist. Skip.")
                            continue

                        interacted, interacted_when = storage.check_user_was_interacted(liker_username)
                        if interacted:
                            can_reinteract = storage.can_be_reinteract(
                                interacted_when,
                                get_value(self.args.can_reinteract_after, None, 0),
                            )
                            if not can_reinteract:
                                logger.info(f"@{liker_username}: already interacted recently. Skip.")
                                continue

                        # Click on liker username to go to profile
                        logger.info(f"@{liker_username}: interact", extra={"color": f"{Fore.YELLOW}"})
                        
                        if username_view.click_retry():
                            # Perform interaction
                            success = self._perform_interaction(
                                device, 
                                storage, 
                                interaction, 
                                is_follow_limit_reached, 
                                liker_username, 
                                target_username
                            )
                            
                            if success:
                                interacted_likers += 1
                                on_interaction(succeed=True, followed=False, scraped=False)
                            
                            # Go back to likers list
                            device.back()
                            random_sleep(1, 2, modulable=False)

                    except Exception as e:
                        logger.debug(f"Error processing liker: {e}")
                        continue

                # Check if we've reached the end or should scroll
                if scroll_end_detector.is_the_end():
                    break
                
                # Scroll down to see more likers
                try:
                    likers_list.scroll(Direction.DOWN)
                    random_sleep(1, 2, modulable=False)
                except Exception as e:
                    logger.debug(f"Error scrolling likers: {e}")
                    break
                    
            except Exception as e:
                logger.debug(f"Error in likers loop: {e}")
                break

        logger.info(f"Interacted with {interacted_likers} likers")
        device.back()  # Go back from likers list

    def _perform_interaction(self, device, storage, interaction, is_follow_limit_reached, username, target):
        """Perform the actual interaction with a user"""
        try:
            can_follow = False
            if is_follow_limit_reached is not None:
                can_follow = not is_follow_limit_reached() and storage.get_following_status(
                    username
                ) in [FollowingStatus.NONE, FollowingStatus.NOT_IN_LIST]

            (
                interaction_succeed,
                followed,
                requested,
                scraped,
                pm_sent,
                number_of_liked,
                number_of_watched,
                number_of_comments,
            ) = interaction(device, username=username, can_follow=can_follow)

            # Add to storage
            storage.add_interacted_user(
                username,
                session_id=self.session_state.id,
                job_name=self.current_mode,
                target=target,
                followed=followed,
                is_requested=requested,
                scraped=scraped,
                liked=number_of_liked,
                watched=number_of_watched,
                commented=number_of_comments,
                pm_sent=pm_sent,
            )

            return interaction_succeed

        except Exception as e:
            logger.error(f"Error during interaction with @{username}: {e}")
            return False