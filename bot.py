import os
import requests
from urllib.parse import quote_plus
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import logging

# ─────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")

# ─────────────────────────────────────────
# BOOK SEARCH
# ─────────────────────────────────────────

def search_books(query):
    try:
        url  = f"https://openlibrary.org/search.json?q={quote_plus(query)}&limit=20"
        r    = requests.get(url, timeout=15)
        data = r.json()
    except Exception as e:
        logger.error(f"Book search error: {e}")
        return []

    if "docs" not in data or len(data["docs"]) == 0:
        return []

    query_words    = set(query.lower().split())
    filtered       = [b for b in data["docs"] if any(w in b.get("title", "").lower() for w in query_words)]
    books_to_show  = filtered[:5] if filtered else data["docs"][:5]

    results = []
    for book in books_to_show:
        try:
            title  = book.get("title") or "Unknown"
            author = ", ".join(book.get("author_name") or ["Unknown"])
            year   = book.get("first_publish_year") or "N/A"
            q      = quote_plus(title)

            entry = (
                f"📖 *{title}*\n"
                f"✍️ Author: {author}\n"
                f"📅 Year: {year}\n\n"
                f"🔗 *Download / Read Links:*\n"
                f"📕 Anna's Archive: https://annas-archive.gl/search?q={q}\n"
                f"🌊 Ocean of PDF: https://oceanofpdf.com/?s={q}\n"
                f"📗 Z-Library: https://z-library.bz/s/{q}\n"
                f"📘 LibGen: https://libgen.im/search.php?req={q}&column=title\n"
                f"📜 Project Gutenberg: https://www.gutenberg.org/ebooks/search/?query={q}"
            )
            results.append(entry)
        except Exception as e:
            logger.warning(f"Skipping book entry due to error: {e}")
            continue

    return [r for r in results if r is not None]  # final safety filter


# ─────────────────────────────────────────
# MOVIE SEARCH
# ─────────────────────────────────────────

def search_movies(query):
    try:
        omdb_url = f"http://www.omdbapi.com/?s={quote_plus(query)}&type=movie&apikey=trilogy"
        r        = requests.get(omdb_url, timeout=15)
        data     = r.json()
    except Exception as e:
        logger.error(f"Movie search error: {e}")
        return []

    movies = []

    if data.get("Response") == "True" and "Search" in data:
        for item in data["Search"][:8]:
            try:
                imdb_id    = item.get("imdbID", "")
                detail_url = f"http://www.omdbapi.com/?i={imdb_id}&apikey=trilogy"
                detail     = requests.get(detail_url, timeout=10).json()
            except Exception:
                detail = item

            try:
                title       = detail.get("Title") or item.get("Title") or "Unknown"
                year        = detail.get("Year") or item.get("Year") or "N/A"
                director    = detail.get("Director") or "N/A"
                genre       = detail.get("Genre") or "N/A"
                language    = detail.get("Language") or "N/A"
                rated       = detail.get("Rated") or "N/A"
                imdb_rating = detail.get("imdbRating") or "N/A"

                non_english   = language != "N/A" and "English" not in language
                subtitle_note = (
                    "✅ Subtitles likely available (non-English film)"
                    if non_english
                    else "⚠️ Subtitles vary by source — check each site"
                )

                movies.append({
                    "title": title, "year": year, "director": director,
                    "genre": genre, "language": language, "rated": rated,
                    "imdb_rating": imdb_rating, "subtitle_note": subtitle_note,
                })
            except Exception as e:
                logger.warning(f"Skipping movie entry due to error: {e}")
                continue

    if not movies:
        return []

    movies.sort(key=lambda x: (
        x["director"].lower() if x["director"] != "N/A" else "zzz",
        x["year"]
    ))

    results = []
    for m in movies:
        try:
            q = quote_plus(m["title"])
            entry = (
                f"🎬 *{m['title']}* ({m['year']})\n"
                f"🎥 Director: {m['director']}\n"
                f"🎭 Genre: {m['genre']}\n"
                f"🌐 Language: {m['language']}\n"
                f"🔞 Rated: {m['rated']}\n"
                f"⭐ IMDb: {m['imdb_rating']}\n"
                f"💬 {m['subtitle_note']}\n\n"
                f"🔗 *Watch / Download Links:*\n"
                f"🎞️ Flixer: https://flixer.sh/search?q={q}\n"
                f"🍿 Cineby: https://www.cineby.gd/search?q={q}\n"
                f"📽️ HDHub4u: https://new4.hdhub4u.fo/?utm=gs&s={q}\n"
                f"🎦 1Movies: https://1movies.bz/search?q={q}\n"
                f"📺 5Movierulz: https://www.5movierulz.insure/?s={q}"
            )
            results.append(entry)
        except Exception as e:
            logger.warning(f"Skipping movie result formatting: {e}")
            continue

    return [r for r in results if r is not None]  # final safety filter


# ─────────────────────────────────────────
# DUAL SEARCH
# ─────────────────────────────────────────

def dual_search(query):
    try:
        book_results  = search_books(query)  or []
        movie_results = search_movies(query) or []

        # Strictly filter out any None or empty entries
        book_results  = [b for b in book_results  if b and isinstance(b, str)]
        movie_results = [m for m in movie_results if m and isinstance(m, str)]

        has_books  = len(book_results)  > 0
        has_movies = len(movie_results) > 0

        output = ""

        if has_books and has_movies:
            output += (
                f"🔍 *'{query}' exists as both a Book & a Film!*\n"
                f"Showing all results below:\n\n"
            )
            output += "━━━━━━━━━━━━━━━━\n"
            output += "📚 *BOOK RESULTS*\n"
            output += "━━━━━━━━━━━━━━━━\n\n"
            output += "\n\n━━━━━━━━━━━━━━━━\n\n".join(book_results)
            output += "\n\n━━━━━━━━━━━━━━━━\n"
            output += "🎬 *FILM RESULTS*\n"
            output += "━━━━━━━━━━━━━━━━\n\n"
            output += "\n\n━━━━━━━━━━━━━━━━\n\n".join(movie_results)

        elif has_books:
            output += "📚 *BOOK RESULTS*\n━━━━━━━━━━━━━━━━\n\n"
            output += "\n\n━━━━━━━━━━━━━━━━\n\n".join(book_results)

        elif has_movies:
            output += "🎬 *FILM RESULTS*\n━━━━━━━━━━━━━━━━\n\n"
            output += "\n\n━━━━━━━━━━━━━━━━\n\n".join(movie_results)

        else:
            output = "❌ No results found for that title. Try a different spelling or keyword."

        return output

    except Exception as e:
        logger.error(f"dual_search failed: {e}")
        return "⚠️ Something went wrong during search. Please try again."


# ─────────────────────────────────────────
# ERROR HANDLER
# ─────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update caused error: {context.error}")
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "⚠️ An error occurred while processing your request. Please try again."
        )


# ─────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to Book & Movie Finder Bot!*\n\n"
        "🔍 *Search anything — just type a title!*\n"
        "If it exists as both a book and a film, you'll get *all results* at once.\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "You can also use specific commands:\n"
        "📚 `/book <title>` — Books only\n"
        "🎬 `/movie <title>` — Movies only\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "📚 *Book Sources:*\n"
        "• Anna's Archive\n• Ocean of PDF\n• Z-Library\n• LibGen\n• Project Gutenberg\n\n"
        "🎬 *Movie Sources:*\n"
        "• Flixer\n• Cineby\n• HDHub4u\n• 1Movies\n• 5Movierulz\n\n"
        "🎯 Movie results sorted by Director & Year",
        parse_mode="Markdown"
    )

async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "❗ Please provide a book title.\nExample: `/book Dune`",
            parse_mode="Markdown"
        )
        return
    await update.message.reply_text("🔎 Searching books...")
    result = search_books(query)
    if not result:
        await update.message.reply_text("❌ No books found. Try a different title.")
        return
    output  = "📚 *BOOK RESULTS*\n━━━━━━━━━━━━━━━━\n\n"
    output += "\n\n━━━━━━━━━━━━━━━━\n\n".join(result)
    await send_long_message(update, output)

async def movie_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "❗ Please provide a movie title.\nExample: `/movie Interstellar`",
            parse_mode="Markdown"
        )
        return
    await update.message.reply_text("🔎 Searching movies...")
    result = search_movies(query)
    if not result:
        await update.message.reply_text("❌ No movies found. Try a different title.")
        return
    output  = "🎬 *FILM RESULTS*\n━━━━━━━━━━━━━━━━\n\n"
    output += "\n\n━━━━━━━━━━━━━━━━\n\n".join(result)
    await send_long_message(update, output)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        return
    await update.message.reply_text("🔎 Searching books & films...")
    result = dual_search(query)
    await send_long_message(update, result)


# ─────────────────────────────────────────
# HELPER: SPLIT LONG MESSAGES
# ─────────────────────────────────────────

async def send_long_message(update: Update, text: str):
    try:
        if len(text) <= 4096:
            await update.message.reply_text(text, parse_mode="Markdown")
        else:
            chunks = []
            while len(text) > 4096:
                split_at = text.rfind("\n", 0, 4096)
                if split_at == -1:
                    split_at = 4096
                chunks.append(text[:split_at])
                text = text[split_at:].strip()
            chunks.append(text)
            for chunk in chunks:
                if chunk.strip():
                    await update.message.reply_text(chunk, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"send_long_message error: {e}")
        await update.message.reply_text("⚠️ Failed to send results. Please try again.")


# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("book", book_command))
    app.add_handler(CommandHandler("movie", movie_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    app.run_polling()
