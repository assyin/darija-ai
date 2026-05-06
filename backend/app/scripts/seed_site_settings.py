from __future__ import annotations

import asyncio
import sys
from typing import NamedTuple

from sqlalchemy import select

from app.core.db import AsyncSessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.models.site_setting import SiteSetting


class Seed(NamedTuple):
    key: str
    value: str
    value_type: str
    category: str
    label_fr: str
    description: str | None
    is_public: bool


_CTA_TEMPLATE_DARIJA = (
    "## 💼 بغيتي تطبق هاد الشي فالخدمة ديالك؟\n\n"
    "أنا **{{business_owner_name}}**، {{business_owner_role}}، كنعاون الشركات والمهنيين المغاربة "
    "يستعملو AI باش يربحو الوقت والفلوس.\n\n"
    "**شنو نقدر نعاونك فيه:**\n"
    "- 🌐 سايت ويب + chatbot AI للشركة ديالك\n"
    "- 🤖 أتمتة العمليات (CRM، WhatsApp، emails)\n"
    "- 📚 تكوين الفرق ديالك على AI\n"
    "- 💡 استشارة تقنية للشركات الصغيرة والمتوسطة\n\n"
    "📞 **WhatsApp**: [{{contact_whatsapp}}](https://wa.me/{{contact_whatsapp_clean}})\n"
    "📅 **حجز call مجاني**: [{{calendly_url}}]({{calendly_url}})\n"
    "📧 **Email**: [{{contact_email}}](mailto:{{contact_email}})"
)


SEED_SETTINGS: list[Seed] = [
    # Contact (public)
    Seed("contact_whatsapp", "+212 600 000 000", "phone", "contact", "Numéro WhatsApp", "Format international, ex: +212 600 000 000", True),
    Seed("contact_email", "contact@darija-ai.com", "email", "contact", "Email pro", "Email affiché publiquement", True),
    Seed("calendly_url", "", "url", "contact", "Lien Calendly", "URL complète, vide si pas configuré", True),

    # Social (public)
    Seed("linkedin_url", "", "url", "social", "URL LinkedIn", "Profil LinkedIn complet", True),
    Seed("instagram_url", "", "url", "social", "URL Instagram", "Profil Instagram", True),
    Seed("tiktok_url", "", "url", "social", "URL TikTok", "Compte TikTok", True),
    Seed("twitter_url", "", "url", "social", "URL X (Twitter)", "Profil X", True),

    # Branding (public)
    Seed("business_name", "DarijaAI", "string", "branding", "Nom du site", "Nom affiché dans header/footer", True),
    Seed("business_owner_name", "Yassine", "string", "branding", "Nom du fondateur", "Affiché dans CTA et About", True),
    Seed("business_owner_role", "مطور و خبير AI", "string", "branding", "Rôle/titre du fondateur", "En darija, affiché dans CTA", True),
    Seed("business_tagline_darija", "أول منصة لأخبار الذكاء الاصطناعي بالدارجة المغربية", "string", "branding", "Tagline darija", "Affiché homepage hero", True),
    Seed("business_logo_url", "", "url", "branding", "URL du logo", "Image hébergée sur R2", True),

    # SEO (public)
    Seed("seo_default_title", "DarijaAI - أخبار الذكاء الاصطناعي بالدارجة", "string", "seo", "Titre SEO par défaut", "Utilisé sur homepage", True),
    Seed("seo_default_description", "أول منصة مغربية لأخبار AI بالدارجة. كنشرحو ليك التكنولوجيا اللي كتغير العالم.", "string", "seo", "Description SEO par défaut", "Meta description homepage", True),
    Seed("seo_keywords", "AI, IA, ذكاء اصطناعي, دارجة, المغرب, ChatGPT, تكنولوجيا", "string", "seo", "Keywords SEO", "Liste séparée par virgules", True),

    # CTA template — public so the frontend can render it on every article.
    # The article CTA is part of the published content, not a secret.
    Seed(
        "cta_template_darija",
        _CTA_TEMPLATE_DARIJA,
        "markdown",
        "cta",
        "Template CTA Darija",
        "Placeholders: {{business_owner_name}}, {{business_owner_role}}, {{contact_whatsapp}}, {{contact_whatsapp_clean}}, {{calendly_url}}, {{contact_email}}. Affiché en bas de chaque article.",
        True,
    ),

    # Admin (private)
    Seed("admin_notification_email", "", "email", "admin", "Email pour notifications", "Reçoit les notifications de nouveaux drafts", False),
    Seed("articles_per_page", "12", "integer", "admin", "Articles par page", "Pagination homepage et listing", False),
]


async def main() -> int:
    configure_logging()
    log = get_logger("scripts.seed_site_settings")

    inserted = 0
    skipped = 0

    try:
        async with AsyncSessionLocal() as session:
            for seed in SEED_SETTINGS:
                existing = await session.scalar(
                    select(SiteSetting).where(SiteSetting.key == seed.key)
                )
                if existing is not None:
                    log.info(
                        "site_setting.skipped_already_exists",
                        key=seed.key,
                    )
                    skipped += 1
                    continue
                row = SiteSetting(
                    key=seed.key,
                    value=seed.value,
                    value_type=seed.value_type,
                    category=seed.category,
                    label_fr=seed.label_fr,
                    description=seed.description,
                    is_public=seed.is_public,
                )
                session.add(row)
                inserted += 1
                log.info(
                    "site_setting.inserted",
                    key=seed.key,
                    category=seed.category,
                    is_public=seed.is_public,
                )
            await session.commit()

        log.info(
            "seed_site_settings.complete",
            inserted=inserted,
            skipped=skipped,
            total=len(SEED_SETTINGS),
        )
        print(f"{inserted} new settings inserted, {skipped} skipped (already exist)")
        return 0
    except Exception:
        log.exception("seed_site_settings.failed", inserted=inserted, skipped=skipped)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
