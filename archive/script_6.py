
# Create a sample JSON structure document showing what the output will look like

sample_outputs = {
    "schedule_example": [
        {
            "date": "11/01/2025",
            "time": "8:00 PM",
            "opponent": "Blue Devils",
            "location": "Orr Rink",
            "result": "W",
            "score": "5-3"
        },
        {
            "date": "11/04/2025",
            "time": "9:15 PM",
            "opponent": "Ice Hawks",
            "location": "University Rink",
            "result": "L",
            "score": "2-4"
        }
    ],
    "stats_example": [
        {
            "player": "John Smith",
            "games_played": "10",
            "goals": "8",
            "assists": "12",
            "points": "20",
            "penalties": "4"
        },
        {
            "player": "Mike Johnson",
            "games_played": "9",
            "goals": "6",
            "assists": "8",
            "points": "14",
            "penalties": "2"
        }
    ],
    "standings_example": [
        {
            "team": "DSMALL",
            "games_played": "10",
            "wins": "7",
            "losses": "2",
            "ties": "1",
            "points": "15",
            "goals_for": "45",
            "goals_against": "28"
        },
        {
            "team": "Opponents",
            "games_played": "10",
            "wins": "5",
            "losses": "4",
            "ties": "1",
            "points": "11",
            "goals_for": "38",
            "goals_against": "35"
        }
    ]
}

# Save sample outputs
import json

with open('sample_output_structure.json', 'w') as f:
    json.dump(sample_outputs, f, indent=2)

print("Sample JSON Output Structures")
print("="*80)
print("\n1. SCHEDULE OUTPUT (schedule.json):")
print(json.dumps(sample_outputs['schedule_example'], indent=2))

print("\n\n2. PLAYER STATS OUTPUT (player_stats.json):")
print(json.dumps(sample_outputs['stats_example'], indent=2))

print("\n\n3. STANDINGS OUTPUT (standings.json):")
print(json.dumps(sample_outputs['standings_example'], indent=2))

print("\n" + "="*80)
print("These are example structures - actual field names will match")
print("what's found in the website tables.")
print("="*80)

print("\n✅ Saved sample structures to: sample_output_structure.json")
