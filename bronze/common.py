import time
# from requests_html import HTMLSession


class ScrollToBottom:
    """
    Scroll to the bottom of an infinite page. Scroll until view height remains unchanged for at least 3 seconds.
    This time can be changed by using parameter wait_time_seconds.
    """

    def __init__(self, driver, wait_time_seconds: float = 3):
        self.wait_time_seconds = wait_time_seconds
        self.scroll_height = driver.execute_script("return document.body.scrollHeight")
        self.start_time = time.time()
        # print(f"Scroll height set to {self.scroll_height}")

    def __call__(self, driver):
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == self.scroll_height:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            if time.time() - self.start_time >= self.wait_time_seconds:
                return True
            return False
        else:
            # print(f"Scroll height changed from {self.scroll_height} to {new_height}")
            self.scroll_height = new_height
            self.start_time = time.time()
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            return False


# def test_url(url_to_test: str, session=HTMLSession()) -> bool:
#     if session.get(url_to_test).status_code != 200:
#         return False
#     return True
