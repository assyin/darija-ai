from __future__ import annotations

import asyncio
import sys
from typing import TypedDict

from sqlalchemy import select

from app.core.db import AsyncSessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.models.source import Source


class SourceSeed(TypedDict):
    name: str
    rss_url: str | None
    scraping_url: str | None
    needs_html_enrichment: bool


SEED_SOURCES: list[SourceSeed] = [
    # =========================================================================
    # Tier 0 — Global English (existing, kept for general AI coverage).
    # =========================================================================
    {
        "name": "Unite.AI",
        "rss_url": "https://www.unite.ai/feed/",
        "scraping_url": None,
        "needs_html_enrichment": False,
    },
    {
        "name": "VentureBeat AI",
        "rss_url": "https://venturebeat.com/category/ai/feed/",
        "scraping_url": None,
        "needs_html_enrichment": False,
    },
    {
        "name": "TechCrunch AI",
        "rss_url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Hugging Face Blog",
        "rss_url": "https://huggingface.co/blog/feed.xml",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Anthropic News",
        "rss_url": None,
        "scraping_url": "https://www.anthropic.com/news",
        "needs_html_enrichment": False,
    },
    # =========================================================================
    # Tier 1 — Morocco. Tagged so future analytics can compute the % of the
    # publishing pipeline that originates from local sources, which is the
    # primary editorial KPI for the MENA + Francophone-Africa positioning.
    # =========================================================================
    {
        # 200-item feed; covers business + tech + economy with regular AI angles.
        "name": "Médias24",
        "rss_url": "https://medias24.com/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # 200-item feed; magazine-grade FR coverage including tech.
        "name": "TelQuel",
        "rss_url": "https://telquel.ma/feed",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Government feed — strategic signal for the "Digital Morocco 2030"
        # narrative even though daily AI density is low.
        "name": "Maroc.ma",
        "rss_url": "https://www.maroc.ma/fr/rss.xml",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Yabiladi",
        "rss_url": "https://www.yabiladi.com/rss/news.xml",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Bladi",
        "rss_url": "https://www.bladi.net/spip.php?page=backend",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    # =========================================================================
    # Tier 2 — MENA / Arab world.
    # =========================================================================
    {
        # THE reference startup-MENA publication, English. Wamda picks up
        # every Tabby/Tamara/Anghami round before global press does.
        "name": "Wamda",
        "rss_url": "https://www.wamda.com/feed",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Menabytes",
        "rss_url": "https://menabytes.com/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Asharq is Bloomberg's Arabic-language joint venture — high-signal
        # economic + AI coverage across Gulf countries.
        "name": "Asharq Al-Awsat EN",
        "rss_url": "https://english.aawsat.com/feed",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    # =========================================================================
    # Tier 3 — Africa Francophone. Anchors the "panafrican francophone" axis
    # of the editorial line.
    # =========================================================================
    {
        # Reference magazine for francophone Africa; broad coverage but every
        # tech-business story is on-thesis for us.
        "name": "Jeune Afrique",
        "rss_url": "https://www.jeuneafrique.com/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # CIO-focused IT publication for Africa — decision-makers angle.
        "name": "CIO Mag",
        "rss_url": "https://www.cio-mag.com/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # African economy + fintech + AI investments.
        "name": "Financial Afrik",
        "rss_url": "https://www.financialafrik.com/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Afrik.com",
        "rss_url": "https://www.afrik.com/feed",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    # =========================================================================
    # Tier 4a — Francophonie EU (France + Belgium + Switzerland).
    # =========================================================================
    {
        # French Tech ecosystem reference — 200-item feed.
        "name": "Frenchweb",
        "rss_url": "https://www.frenchweb.fr/feed",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Daily FR startup coverage (Station F, Bpifrance, Mistral, etc.).
        "name": "Maddyness",
        "rss_url": "https://www.maddyness.com/feed",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # AI + marketing tech, strong on EU policy (AI Act).
        "name": "Siècle Digital",
        "rss_url": "https://siecledigital.fr/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Tech grand public FR — accessible AI coverage.
        "name": "Numerama",
        "rss_url": "https://www.numerama.com/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Les Numériques",
        "rss_url": "https://www.lesnumeriques.com/rss.xml",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Journal du Net",
        "rss_url": "https://www.journaldunet.com/rss/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "ZDNet FR",
        "rss_url": "https://www.zdnet.fr/feeds/rss/actualites/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Belgian tech reference — Datanews is the FR-Belgian IT/AI magazine.
        "name": "Datanews FR",
        "rss_url": "https://datanews.levif.be/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Major Belgian daily — broader coverage but quality tech/AI section.
        "name": "La Libre",
        "rss_url": "https://www.lalibre.be/rss.xml",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Reference Swiss IT publication.
        "name": "ICT Journal",
        "rss_url": "https://www.ictjournal.ch/rss.xml",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Le Temps is Switzerland's leading FR daily (Geneva-based).
        "name": "Le Temps",
        "rss_url": "https://www.letemps.ch/feed",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    # =========================================================================
    # Tier 4b — Francophonie Quebec / Canada FR. Critical for the AI angle:
    # Mila, Yoshua Bengio, IVADO, Element AI legacy — Quebec is one of the
    # densest AI research hubs in the world.
    # =========================================================================
    {
        # Quebec's reference quality daily, business + tech coverage.
        "name": "Le Devoir",
        "rss_url": "https://www.ledevoir.com/rss/manchettes.xml",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Largest FR daily in North America; dedicated techno section.
        "name": "La Presse Techno",
        "rss_url": "https://www.lapresse.ca/affaires/techno/rss",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Quebec's leading business magazine.
        "name": "Les Affaires",
        "rss_url": "https://www.lesaffaires.com/feed",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        # Canadian public broadcaster's tech feed — high-quality FR coverage
        # of Canadian AI ecosystem (Mila, Vector Institute, Element AI legacy).
        "name": "Radio-Canada Techno",
        "rss_url": "https://ici.radio-canada.ca/rss/4159",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
]


async def main() -> int:
    configure_logging()
    logger = get_logger("scripts.seed_sources")

    created = 0
    updated = 0
    unchanged = 0

    try:
        async with AsyncSessionLocal() as session:
            for seed in SEED_SOURCES:
                existing = await session.scalar(select(Source).where(Source.name == seed["name"]))
                if existing is None:
                    source = Source(
                        name=seed["name"],
                        rss_url=seed["rss_url"],
                        scraping_url=seed["scraping_url"],
                        is_active=True,
                        needs_html_enrichment=seed["needs_html_enrichment"],
                    )
                    session.add(source)
                    await session.flush()
                    logger.info(
                        "source.created",
                        name=source.name,
                        source_id=source.id,
                        rss_url=source.rss_url,
                        scraping_url=source.scraping_url,
                        needs_html_enrichment=source.needs_html_enrichment,
                    )
                    created += 1
                    continue

                changes: dict[str, object] = {}
                if existing.rss_url != seed["rss_url"]:
                    changes["rss_url"] = seed["rss_url"]
                if existing.scraping_url != seed["scraping_url"]:
                    changes["scraping_url"] = seed["scraping_url"]
                if existing.needs_html_enrichment != seed["needs_html_enrichment"]:
                    changes["needs_html_enrichment"] = seed["needs_html_enrichment"]

                if not changes:
                    logger.info(
                        "source.skipped_already_exists",
                        name=seed["name"],
                        source_id=existing.id,
                    )
                    unchanged += 1
                    continue

                for field_name, value in changes.items():
                    setattr(existing, field_name, value)
                session.add(existing)
                logger.info(
                    "source.updated",
                    name=existing.name,
                    source_id=existing.id,
                    changes=changes,
                )
                updated += 1

            await session.commit()

        logger.info(
            "seed.complete",
            created=created,
            updated=updated,
            unchanged=unchanged,
            total=len(SEED_SOURCES),
        )
        return 0
    except Exception:
        logger.exception(
            "seed.failed",
            created=created,
            updated=updated,
            unchanged=unchanged,
        )
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
