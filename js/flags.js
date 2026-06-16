// Best-effort country-name -> flag emoji lookup so match cards look nicer.
// Falls back to a soccer ball icon for any name not in the map (e.g. "TBD").
const FLAGS = {
  "Argentina": "🇦🇷", "Australia": "🇦🇺", "Austria": "🇦🇹", "Belgium": "🇧🇪",
  "Bolivia": "🇧🇴", "Brazil": "🇧🇷", "Cameroon": "🇨🇲", "Canada": "🇨🇦",
  "Chile": "🇨🇱", "Colombia": "🇨🇴", "Costa Rica": "🇨🇷", "Croatia": "🇭🇷",
  "Curacao": "🇨🇼", "Denmark": "🇩🇰", "Ecuador": "🇪🇨", "Egypt": "🇪🇬",
  "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "France": "🇫🇷", "Germany": "🇩🇪", "Ghana": "🇬🇭",
  "Haiti": "🇭🇹", "Honduras": "🇭🇳", "Iceland": "🇮🇸", "Iran": "🇮🇷",
  "Iraq": "🇮🇶", "Italy": "🇮🇹", "Ivory Coast": "🇨🇮", "Jamaica": "🇯🇲",
  "Japan": "🇯🇵", "Jordan": "🇯🇴", "Mexico": "🇲🇽", "Morocco": "🇲🇦",
  "Netherlands": "🇳🇱", "New Zealand": "🇳🇿", "Nigeria": "🇳🇬",
  "North Macedonia": "🇲🇰", "Norway": "🇳🇴", "Panama": "🇵🇦",
  "Paraguay": "🇵🇾", "Peru": "🇵🇪", "Poland": "🇵🇱", "Portugal": "🇵🇹",
  "Qatar": "🇶🇦", "Saudi Arabia": "🇸🇦", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
  "Senegal": "🇸🇳", "Serbia": "🇷🇸", "South Africa": "🇿🇦",
  "South Korea": "🇰🇷", "Spain": "🇪🇸", "Suriname": "🇸🇷", "Sweden": "🇸🇪",
  "Switzerland": "🇨🇭", "Tunisia": "🇹🇳", "Turkey": "🇹🇷", "Ukraine": "🇺🇦",
  "United States": "🇺🇸", "USA": "🇺🇸", "Uruguay": "🇺🇾", "Uzbekistan": "🇺🇿",
  "Venezuela": "🇻🇪", "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
};

export function flagFor(teamName) {
  if (!teamName) return "⚽";
  return FLAGS[teamName.trim()] || "⚽";
}
