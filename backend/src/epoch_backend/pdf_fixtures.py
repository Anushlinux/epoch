"""Synthetic source briefs and short source PDFs, never generated repair candidates."""

import inspect

from epoch_backend.pdf_baseline import render_pdf


def brief(pack):
    if pack == "retreat":
        blocks = [
            {"kind": "heading", "text": "Three-day retreat for 48 people"},
            {
                "kind": "paragraph",
                "text": (
                    "Client: Northstar Studio. Dates: 12-14 November. Location: "
                    "Lakeside Lodge. Budget ceiling: INR 720000. Preserve every "
                    "itinerary entry, accommodation option, budget line and "
                    "cancellation condition below. These are synthetic planning facts."
                ),
            },
        ]
        activities = [
            "Breakfast and arrival check-in",
            "Team strategy workshop",
            "Coffee and collaboration break",
            "Product planning session",
            "Lunch with dietary options",
            "Guided outdoor team challenge",
            "Reflection and quiet working time",
            "Dinner and evening conversation",
        ]
        for day in range(1, 4):
            blocks.append({"kind": "heading", "text": f"Day {day} itinerary"})
            blocks.append(
                {
                    "kind": "bullets",
                    "items": [
                        f"Day {day}, session {i + 1}: {activity}. "
                        "Allocate 60 minutes; the retreat coordinator confirms attendance "
                        "and accessibility requirements before the session."
                        for i, activity in enumerate(activities)
                    ],
                }
            )
        blocks += [
            {"kind": "heading", "text": "Accommodation options"},
            {
                "kind": "bullets",
                "items": [
                    "Option A: 24 twin rooms, two nights, INR 288000 total, breakfast included.",
                    "Option B: 16 triple rooms, two nights, INR 240000 total, breakfast included.",
                    (
                        "Reserve two accessible rooms within the chosen option; step-free "
                        "access is required."
                    ),
                ],
            },
            {"kind": "heading", "text": "Budget breakdown"},
            {
                "kind": "table",
                "rows": [
                    ["Item", "Amount"],
                    ["Accommodation option A", "INR 288000"],
                    ["Meals", "INR 172800"],
                    ["Transport", "INR 72000"],
                    ["Venue and equipment", "INR 60000"],
                    ["Activities", "INR 48000"],
                    ["Contingency", "INR 79200"],
                    ["Total", "INR 720000"],
                ],
            },
            {"kind": "heading", "text": "Cancellation terms"},
            {
                "kind": "bullets",
                "items": [
                    "Cancel at least 30 days before arrival: 90 percent refund.",
                    "Cancel 15-29 days before arrival: 50 percent refund.",
                    "Cancel fewer than 15 days before arrival: no refund.",
                    "Guest substitutions are permitted until 48 hours before arrival.",
                    (
                        "Final confirmation must include dietary requirements and "
                        "accessibility arrangements."
                    ),
                ],
            },
        ]
        return {"title": "Northstar Studio Retreat Brief", "blocks": blocks}
    blocks = [
        {"kind": "heading", "text": "College festival sponsorship brief"},
        {
            "kind": "paragraph",
            "text": (
                "Client: Riverside College. Event: Horizon Festival. Attendance: "
                "2400 students. Date: 21 February. Preserve all five packages, "
                "benefits and payment conditions below. These are synthetic "
                "planning facts."
            ),
        },
    ]
    for name, price in [
        ("Title", "500000"),
        ("Platinum", "300000"),
        ("Gold", "180000"),
        ("Silver", "100000"),
        ("Community", "40000"),
    ]:
        blocks += [
            {"kind": "heading", "text": f"{name} package: INR {price}"},
            {
                "kind": "bullets",
                "items": [
                    f"{name} benefit {i + 1}: {item}. "
                    "Confirm final wording with the festival team seven days before the event."
                    for i, item in enumerate(
                        [
                            "Brand placement on the event website",
                            "Sponsor introduction during the opening session",
                            "Dedicated exhibition space with power",
                            "Student engagement activity coordinated by volunteers",
                            "Post-event attendance and engagement report",
                            "Named coordinator for logistics and approvals",
                        ]
                    )
                ],
            },
        ]
    blocks += [
        {"kind": "heading", "text": "Payment and cancellation"},
        {
            "kind": "paragraph",
            "text": (
                "Payment: 50 percent on confirmation and 50 percent ten days "
                "before the festival. Cancellation before 1 February receives a 75"
                " percent refund. The college retains approval over all displayed "
                "materials."
            ),
        },
    ]
    return {"title": "Horizon Festival Sponsorship Brief", "blocks": blocks}


PACK_FILES = {
    "retreat": [
        (
            "hotel-brochure.pdf",
            "Lakeside Lodge",
            (
                "24 twin rooms. Two accessible rooms. Breakfast included. Lakeside"
                " conference room seats 60 guests."
            ),
        ),
        (
            "venue-map.pdf",
            "Venue map",
            (
                "Reception -> Conference hall -> Dining room. Accessible path "
                "connects all three buildings."
            ),
        ),
    ],
    "festival": [
        (
            "speaker-profiles.pdf",
            "Speaker profiles",
            "Maya Rao: product design. Arjun Mehta: sustainable engineering.",
        ),
        (
            "event-schedule.pdf",
            "Festival schedule",
            "09:00 Registration. 10:00 Opening. 11:00 Talks. 14:00 Workshops. 17:00 Closing.",
        ),
        (
            "sponsor-brochure.pdf",
            "Sponsor brochure",
            (
                "Title, Platinum, Gold, Silver and Community packages. Contact the"
                " college festival team."
            ),
        ),
    ],
}


def source_pdf(runtime, name, title, content):
    if name == "venue-map.pdf":
        source = """def render_pdf(document):
 import io
 from reportlab.pdfgen.canvas import Canvas
 from reportlab.lib.pagesizes import A4
 out=io.BytesIO(); c=Canvas(out,pagesize=A4)
 c.setFont("Helvetica-Bold",20); c.drawString(42,790,"Lakeside Lodge - venue map")
 c.setFont("Helvetica",12)
 for x,y,label in [(50,590,"Reception"),(320,590,"Conference hall"),(180,350,"Dining room")]:
  c.setFillColorRGB(.90,.94,.92); c.rect(x,y,150,100,fill=1)
  c.setFillColorRGB(.1,.2,.2); c.drawString(x+12,y+45,label)
 c.setLineWidth(5); c.line(200,640,320,640); c.line(395,590,255,450)
 c.drawString(42,270,"Step-free paths connect all buildings.")
 c.save(); return out.getvalue()
"""
    else:
        source = inspect.getsource(render_pdf)
    return runtime.execute(
        source,
        "render_pdf",
        document={"title": title, "blocks": [{"kind": "paragraph", "text": content}]},
    )


def prompt(pack):
    title = (
        "Northstar Studio Retreat Brief"
        if pack == "retreat"
        else "Horizon Festival Sponsorship Brief"
    )
    return (
        f"Read the {title} using documents.list and documents.read. "
        "Create a client-ready PDF preserving every supplied section, itinerary entry "
        "or package benefit, budget figure and condition. Use the complete supplied "
        "document content without shortening it. Report the actual PDF result."
    )
