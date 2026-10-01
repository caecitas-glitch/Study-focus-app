package com.focusflow.companion.workers

import kotlin.random.Random

data class MotivationalQuote(
    val shortQuote: String,
    val author: String,
    val fullQuote: String = shortQuote
)

object QuoteBank {
    // Punchy, short quotes specifically tailored to fit the Android notification bar without truncation
    private val quotes = listOf(
        MotivationalQuote("Discipline equals freedom.", "Jocko Willink"),
        MotivationalQuote("Action cures fear. Start now.", "David Schwartz"),
        MotivationalQuote("Focus on the process, not the outcome.", "Unknown"),
        MotivationalQuote("Small daily wins lead to massive results.", "Robin Sharma"),
        MotivationalQuote("Stay in the fight. Lock in.", "David Goggins"),
        MotivationalQuote("Energy flows where attention goes.", "Tony Robbins"),
        MotivationalQuote("Make today count.", "Muhammad Ali"),
        MotivationalQuote("Show up every day, no matter what.", "Seneca"),
        MotivationalQuote("Don't count the days, make days count.", "Muhammad Ali"),
        MotivationalQuote("Consistency is your superpower.", "Unknown"),
        MotivationalQuote("The secret of getting ahead is starting.", "Mark Twain"),
        MotivationalQuote("Discipline weighs ounces, regret tons.", "Jim Rohn"),
        MotivationalQuote("One focused hour changes everything.", "Unknown"),
        MotivationalQuote("Do what others won't so you can succeed.", "Tim Grover"),
        MotivationalQuote("Master your morning, conquer your day.", "Unknown"),
        MotivationalQuote("Progress over perfection.", "Unknown"),
        MotivationalQuote("Your future is built today, not tomorrow.", "Unknown"),
        MotivationalQuote("What stands in the way becomes the way.", "Marcus Aurelius"),
        MotivationalQuote("Endure and conquer.", "Bruce Lee"),
        MotivationalQuote("Victory belongs to the disciplined.", "Napoleon")
    )

    fun getRandomQuote(): MotivationalQuote {
        return quotes[Random.nextInt(quotes.size)]
    }

    fun getNotificationText(): Pair<String, String> {
        val q = getRandomQuote()
        return Pair(q.shortQuote, q.author)
    }

    fun formatQuote(): String {
        val q = getRandomQuote()
        return "\"${q.shortQuote}\" — ${q.author}"
    }
}
