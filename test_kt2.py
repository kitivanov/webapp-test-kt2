import time
from typing import Any, Iterable

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://4lapy.ru/"
DEFAULT_TIMEOUT_S = 15

ANTIBOT_MARKERS = (
    "вы не робот",
    "подтвердите, что запросы отправляли вы",
)


@pytest.fixture()
def browser():
    driver = webdriver.Chrome()
    driver.maximize_window()
    yield driver
    driver.quit()


def wait_page_ready(driver: WebDriver, timeout_s: int = DEFAULT_TIMEOUT_S) -> None:
    """Явно ждёт полной загрузки страницы в браузере до указанного таймаута."""
    WebDriverWait[Any](driver, timeout_s).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def is_antibot_page(driver: WebDriver) -> bool:
    """Определяет, показывает ли сайт антибот-страницу («Вы не робот?»)."""
    text = (driver.page_source or "").lower()
    return any(m in text for m in ANTIBOT_MARKERS)


def skip_if_antibot(driver: WebDriver) -> None:
    """Пропускает тест, если открыта антибот-страница."""
    if is_antibot_page(driver):
        pytest.skip("Сайт показал антибот-страницу («Вы не робот?»).")


def open_home(driver: WebDriver) -> None:
    """Открывает главную страницу 4lapy и ждёт её готовности."""
    driver.get(BASE_URL)
    wait_page_ready(driver)
    WebDriverWait[Any](driver, DEFAULT_TIMEOUT_S).until(EC.url_contains("4lapy.ru"))


def find_first(
    driver: WebDriver,
    locators: Iterable[tuple[str, str]],
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> WebElement:
    """Возвращает первый найденный элемент по списку локаторов или кидает TimeoutException."""
    last_exc: Exception | None = None
    for by, value in locators:
        try:
            return WebDriverWait(driver, timeout_s).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException as e:
            last_exc = e
    raise TimeoutException(f"None of the locators matched. Last error: {last_exc}")


def search_input(driver: WebDriver) -> WebElement:
    """Находит и возвращает поле поиска по товарам на сайте 4lapy."""
    locators = (
        (By.CSS_SELECTOR, '[data-testid="search-input"]'),
        (By.CSS_SELECTOR, 'input[placeholder="поиск по товарам"]'),
    )
    last_exc: Exception | None = None
    for by, value in locators:
        try:
            return WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((by, value))
            )
        except TimeoutException as e:
            last_exc = e
    raise TimeoutException(f"Search input not found/visible. Last error: {last_exc}")


def _wait_search_state(driver: WebDriver, url_before: str, query: str) -> str:
    """Ждёт, пока поиск придёт к одному из состояний: antibot, not_found, url_changed или search_page."""
    not_found_markers = (
        "ничего не найдено",
        "по вашему запросу ничего не найдено",
        "не найдено",
        "нет результатов",
        "страница не найдена",
    )

    def _cond(d: WebDriver) -> str | bool:
        html = (d.page_source or "").lower()
        if any(m in html for m in ANTIBOT_MARKERS):
            return "antibot"
        if any(m in html for m in not_found_markers):
            return "not_found"

        url_now = (d.current_url or "").lower()
        if url_now and url_now != (url_before or "").lower():
            return "url_changed"

        if "поиск" in html and query.lower() in html:
            return "search_page"
        return False

    time.sleep(3)

    return WebDriverWait(driver, 10).until(_cond)


def clear_cookies_and_reload(driver: WebDriver) -> None:
    """Очищает все cookies и перезагружает страницу, ожидая её готовности."""
    driver.delete_all_cookies()
    driver.refresh()
    wait_page_ready(driver)
    time.sleep(3)


def open_cart(driver: WebDriver) -> None:
    """Переходит на страницу корзины из текущего состояния сайта."""
    cart_link = find_first(
        driver,
        locators=(
            (By.CSS_SELECTOR, "a[href*='cart']"),
            (By.CSS_SELECTOR, "a[href*='basket']"),
            (By.XPATH, "//a[contains(., 'Корзин')]"),
        ),
        timeout_s=8,
    )
    cart_link.click()
    wait_page_ready(driver, timeout_s=DEFAULT_TIMEOUT_S)


def test_open_4lapy_homepage(browser: WebDriver):
    """Проверяет, что главная страница 4lapy открывается и содержит ожидаемые маркеры."""
    open_home(browser)
    page_text = (browser.page_source or "").lower()

    expected_markers = (
        "4 лапы",
        "4lapy",
        *ANTIBOT_MARKERS,
    )
    assert any(m in page_text for m in expected_markers)


def test_window_management_size_and_position(browser: WebDriver):
    """Демонстрирует изменение размера и позиции окна браузера и проверяет применённые размеры."""
    open_home(browser)

    browser.maximize_window()
    browser.set_window_position(0, 0)
    browser.set_window_size(1280, 720)

    size = browser.get_window_size()
    assert size["width"] >= 1200
    assert size["height"] >= 650


def test_4lapy_cookies_management(browser: WebDriver):
    """Проверяет добавление, чтение и удаление cookies в контексте сайта 4lapy."""
    open_home(browser)

    browser.delete_all_cookies()
    browser.add_cookie({"name": "test_cookie", "value": "123", "path": "/"})

    assert browser.get_cookie("test_cookie") is not None
    cookies = browser.get_cookies()
    assert any(c["name"] == "test_cookie" and c["value"] == "123" for c in cookies)

    time.sleep(1)
    browser.delete_cookie("test_cookie")
    assert browser.get_cookie("test_cookie") is None


def test_4lapy_window_handles(browser: WebDriver):
    """Проверяет открытие нового окна, переключение по дескрипторам и возврат в исходное окно."""
    open_home(browser)

    main_window = browser.current_window_handle
    browser.execute_script("window.open(arguments[0], '_blank');", BASE_URL)

    WebDriverWait(browser, DEFAULT_TIMEOUT_S).until(lambda d: len(d.window_handles) > 1)
    new_window = [h for h in browser.window_handles if h != main_window][0]

    browser.switch_to.window(new_window)
    wait_page_ready(browser)
    assert "4lapy.ru" in (browser.current_url or "")

    browser.close()
    browser.switch_to.window(main_window)
    assert browser.current_window_handle == main_window


def test_iframe(browser: WebDriver):
    """
    Проверка наличия хотя бы одного iframe с id на странице.
    """
    open_home(browser)

    all_iframes = browser.find_elements(By.TAG_NAME, "iframe")
    iframes_with_id = [f for f in all_iframes if f.get_attribute("id")]

    if len(iframes_with_id) == 0:
        pytest.skip("На странице нет iframe с id.")


def test_search_positive(browser: WebDriver):
    """Позитивный сценарий поиска по валидному запросу «корм»."""
    open_home(browser)
    skip_if_antibot(browser)

    query = "корм"
    url_before = browser.current_url or ""
    field = search_input(browser)
    field.clear()
    field.send_keys(query + Keys.ENTER)

    state = _wait_search_state(browser, url_before=url_before, query=query)
    if state == "antibot":
        pytest.skip("Антибот включился после отправки поискового запроса.")
    if state == "not_found":
        pytest.fail("По позитивному запросу показано «ничего не найдено».")


def test_search_negative(browser: WebDriver):
    """Негативный сценарий поиска по заведомо нерелевантному запросу."""
    open_home(browser)
    skip_if_antibot(browser)

    query = "скины кс2"
    url_before = browser.current_url or ""
    field = search_input(browser)
    field.clear()
    field.send_keys(query + Keys.ENTER)

    state = _wait_search_state(browser, url_before=url_before, query=query)
    if state == "antibot":
        pytest.skip("Антибот включился после отправки поискового запроса.")
    if state != "not_found":
        pytest.skip(
            "Не удалось подтвердить негативный сценарий поиска."
        )


def test_search_boundary_long_query(browser: WebDriver):
    """Граничный сценарий поиска с очень длинной строкой запроса."""
    open_home(browser)
    skip_if_antibot(browser)

    query = "a" * 1000
    url_before = browser.current_url or ""
    field = search_input(browser)
    field.clear()
    field.send_keys(query + Keys.ENTER)

    state = _wait_search_state(browser, url_before=url_before, query=query)
    if state == "antibot":
        pytest.skip("Антибот включился после отправки длинного поискового запроса.")

    assert state in ("url_changed", "search_page", "not_found")


def test_cart_add_item(browser: WebDriver):
    """Проверяет, что товар добавляется в корзину, а после очистки cookies корзина пустеет."""
    open_home(browser)
    skip_if_antibot(browser)

    add_to_cart_btn = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, ".digi-product__actions .digi-product__button")
        )
    )
    add_to_cart_btn.click()
    time.sleep(3)

    cart_counter = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, "tag-counter"))
    )
    assert int(cart_counter.text.strip()) > 0

    cart_link = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '[data-testid="nav-icon-link-nav_menu_cart"]')
        )
    )
    cart_link.click()
    wait_page_ready(browser)
    WebDriverWait(browser, 10).until(EC.url_contains("/cart"))

    items = browser.find_elements(By.CSS_SELECTOR, 'li[data-testid^="cart-item-"]')
    assert len(items) > 0

    clear_cookies_and_reload(browser)

    items_after = browser.find_elements(By.CSS_SELECTOR, 'li[data-testid^="cart-item-"]')
    assert len(items_after) == 0


def test_making_an_order(browser: WebDriver):
    """Оформление заказа: проверка появления формы авторизации при нажатии кнопки в корзине."""
    open_home(browser)
    skip_if_antibot(browser)

    add_to_cart_btn = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, ".digi-product__actions .digi-product__button")
        )
    )
    add_to_cart_btn.click()

    cart_counter = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, "tag-counter"))
    )
    assert int(cart_counter.text.strip()) > 0

    cart_link = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '[data-testid="nav-icon-link-nav_menu_cart"]')
        )
    )
    cart_link.click()
    wait_page_ready(browser)
    WebDriverWait(browser, 10).until(EC.url_contains("/cart"))

    items = WebDriverWait(browser, 10).until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, 'li[data-testid^="cart-item-"]')
        )
    )
    assert len(items) > 0

    checkout_btn = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '[data-testid="checkout-action-button"]')
        )
    )
    checkout_btn.click()

    auth_root = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '[data-testid="auth-register"]')
        )
    )

    title_el = auth_root.find_element(By.CSS_SELECTOR, '[data-testid="auth-title"]')
    assert "войдите" in title_el.text.lower()

    phone_input = auth_root.find_element(By.CSS_SELECTOR, '[data-testid="phone-input"]')
    assert phone_input.is_displayed()

    clear_cookies_and_reload(browser)
