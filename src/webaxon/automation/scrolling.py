from time import sleep


def scroll_down(driver, step_height: int = 0, wait_interval: int = 3):
    if step_height == 0:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(wait_interval)
    else:
        total_height = driver.execute_script("return document.body.scrollHeight")
        scroll_height = 300
        for i in range(0, total_height, scroll_height):
            driver.execute_script(f"window.scrollTo(0, {i});")
            sleep(wait_interval)


def scroll_up(driver, step_height: int = 0, wait_interval: int = 3):
    if step_height == 0:
        driver.execute_script("window.scrollTo(0, 0);")  # Scroll all the way to the top
        sleep(wait_interval)
    else:
        total_height = driver.execute_script("return document.body.scrollHeight")
        for i in range(total_height, 0, -step_height):
            driver.execute_script(f"window.scrollTo(0, {i});")
            sleep(wait_interval)
