import re
import os
import asyncio
import requests
from playwright.async_api import async_playwright

# --- НАСТРОЙКИ УЧЕТНОЙ ЗАПИСИ ---
EMAIL = ""  # Укажите ваш Email от аккаунта optovi4ok.top
PASSWORD = ""  # Укажите ваш пароль

OUTPUT_DIR = "Готовые_товары_для_Viber"
TEXTS_DIR = os.path.join(OUTPUT_DIR, "Тексты_описаний")


def save_product_to_folder(idx, title, price_str, desc_text, image_urls):
    """Создает папку для товара с картинками, а текст сохраняет в отдельную общую папку"""
    # Очищаем название от запрещенных символов для папок/файлов
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title.strip())

    # 1. Папка для картинок товара
    folder_name = os.path.join(OUTPUT_DIR, f"Товар_{idx}_{safe_title}")
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    # 2. Папка для всех текстовых файлов
    if not os.path.exists(TEXTS_DIR):
        os.makedirs(TEXTS_DIR)

    # Сохраняем текстовое описание в отдельную папку Тексты_описаний
    text_file_path = os.path.join(TEXTS_DIR, f"Товар_{idx}_{safe_title}.txt")
    full_text = f"{title.strip()}\n{price_str}\n\n{desc_text}"
    with open(text_file_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    # 3. Скачиваем все картинки в папку товара
    downloaded_count = 0
    for img_idx, url in enumerate(image_urls, 1):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img_path = os.path.join(folder_name, f"фото_{img_idx}.jpg")
                with open(img_path, "wb") as f:
                    f.write(response.content)
                downloaded_count += 1
        except Exception as e:
            print(f"Ошибка скачивания фото: {e}")

    print(
        f"[Успешно] Товар #{idx}: папка с фото создана, а текст сохранен в 'Тексты_описаний' (Фотографий: {downloaded_count})")


async def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("--> Переход на страницу входа...")
        await page.goto("https://optovi4ok.top/index.php?route=account/login", wait_until="networkidle")

        if "login" in page.url or await page.locator('input[type="email"], input[name="email"]').count() > 0:
            print("--> Заполнение формы входа...")
            try:
                await page.fill('input[name="email"], input#input-email, input[type="email"]', EMAIL)
                await page.fill('input[name="password"], input#input-password, input[type="password"]', PASSWORD)
                await page.click('input[type="submit"], button[type="submit"], .btn-primary')
                await page.wait_for_load_state("networkidle")
                print("--> Авторизация успешно выполнена!\n")
            except Exception as e:
                print(f"--> Ошибка авторизации: {e}\n")
        else:
            print("--> Уже авторизованы в системе!\n")

        print("--> Переход в каталог...")
        await page.goto("https://optovi4ok.top/", wait_until="networkidle")
        await asyncio.sleep(2)

        product_elements = await page.locator(".product-item").all()
        product_links = []
        for elem in product_elements:
            href = await elem.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = "https://optovi4ok.top/" + href.lstrip("/")
                product_links.append(href)

        print(f"Найдено товаров: {len(product_links)}\n" + "=" * 50)

        for idx, link in enumerate(product_links, 1):
            try:
                item_page = await context.new_page()
                await item_page.goto(link, wait_until="networkidle")

                # Название
                title_elem = item_page.locator("h1").first
                title_text = await title_elem.inner_text() if await title_elem.count() > 0 else "Товар"

                # Цена и наценка (+35 если > 500, иначе +25)
                body_text = await item_page.inner_text("body")
                price_match = re.search(r'(\d+)\s*грн', body_text)

                final_price_str = "Цена не найдена"
                if price_match:
                    base_price = int(price_match.group(1))
                    if base_price > 500:
                        final_price = base_price + 35
                    else:
                        final_price = base_price + 25
                    final_price_str = f"{final_price} грн"

                # Описание
                desc_elem = item_page.locator("form.form-horizontal .text-gray.pt-4").first
                if await desc_elem.count() > 0:
                    desc_text = await desc_elem.inner_text()
                    desc_text = "\n".join([line.strip() for line in desc_text.splitlines() if line.strip()])
                else:
                    desc_text = "Описание отсутствует"

                # Все фотографии товара
                source_elems = await item_page.locator(".swiper-slide picture source").all()
                images = []
                for source in source_elems:
                    srcset = await source.get_attribute("srcset")
                    if srcset:
                        src_clean = srcset.split()[0]
                        if not src_clean.startswith("http"):
                            src_clean = "https://optovi4ok.top/" + src_clean.lstrip("/")
                        if src_clean not in images:
                            images.append(src_clean)

                # Сохраняем товар (фото в папку товара, текст в общую папку с текстами)
                save_product_to_folder(idx, title_text, final_price_str, desc_text, images)

                await item_page.close()

            except Exception as e:
                print(f"Ошибка при обработке товара #{idx}: {e}")
                continue

        print("\n--> Готово! Картинки разложены по папкам товаров, а все тексты собраны в папке 'Тексты_описаний'.")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())