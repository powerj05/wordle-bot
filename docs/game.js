// JavaScript implementation of the Python classes
class LetterState {
    constructor(character) {
        this.character = character;
        this.is_in_word = false;
        this.is_in_position = false;
    }
}

class Wordle {
    constructor(secret) {
        this.MAX_ATTEMPTS = 6;
        this.WORD_LENGTH = 5;
        this.VOIDED_LETTER = "*";
        this.secret = secret.toUpperCase();
        this.attempts = [];
    }

    attempt(word) {
        word = word.toUpperCase();
        this.attempts.push(word);
    }

    guess(word) {
        word = word.toUpperCase();
        // Initialize the results array with all GREY letters.
        const result = [...word].map(char => new LetterState(char));
        // Make a copy of the secret so we can cross out 'used' letters.
        const remaining_secret = [...this.secret];

        // First, check for GREEN letters.
        for (let i = 0; i < this.WORD_LENGTH; i++) {
            const letter = result[i];
            if (letter.character === remaining_secret[i]) {
                letter.is_in_position = true;
                remaining_secret[i] = this.VOIDED_LETTER;
            }
        }

        // Loop again and check for YELLOW letters.
        for (let i = 0; i < this.WORD_LENGTH; i++) {
            const letter = result[i];
            // Skip this letter if it is already in the right place.
            if (letter.is_in_position) {
                continue;
            }
            // Otherwise, check if the letter is in the word, and void that index.
            for (let j = 0; j < this.WORD_LENGTH; j++) {
                if (letter.character === remaining_secret[j]) {
                    remaining_secret[j] = this.VOIDED_LETTER;
                    letter.is_in_word = true;
                    break;
                }
            }
        }

        return result;
    }

    get is_solved() {
        return this.attempts.length > 0 && this.attempts[this.attempts.length - 1] === this.secret;
    }

    get remaining_attempts() {
        return this.MAX_ATTEMPTS - this.attempts.length;
    }

    get can_attempt() {
        return this.remaining_attempts > 0 && !this.is_solved;
    }
}

function getSeededRandom(seed) {
    let h = 0;
    for (let i = 0; i < seed.length; i++) {
        h = (31 * h + seed.charCodeAt(i)) >>> 0;
    }
    return () => {
        h = (h * 1664525 + 1013904223) % 4294967296;
        return h / 4294967296;
    };
}

function getShuffledWordList(words, seed = "Wordle2025") {
    const rng = getSeededRandom(seed);
    const shuffled = [...words];
    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
}

function getTodayIndex(startDate = "2025-07-15") {
    const base = new Date(startDate);
    const today = new Date();
    return Math.floor((today - base) / (1000 * 60 * 60 * 24));
}

// Game state
let game;
let currentRow = 0;
let currentGuess = '';
let gameOver = false;
let finalScore = null; // This will store the final score
let allowedWords = [];
let secretWord = "";

// Initialize Telegram Web App
const tg = window.Telegram.WebApp;
tg.expand();

// DOM elements
const gameBoard = document.getElementById('gameBoard');
const keyboard = document.getElementById('keyboard');
const message = document.getElementById('message');
const attemptCount = document.getElementById('attemptCount');
const remainingAttempts = document.getElementById('remainingAttempts');

// Initialize game
function initGame(secret) {
    /*Fetch answers list
    Fetch legal guesses list
    selectword() */

    game = new Wordle(secret);
    currentRow = 0;
    currentGuess = '';
    gameOver = false;
    finalScore = null;
    
    createBoard();
    updateStats();
    hideMessage();
    
}

// Create the game board
function createBoard() {
    gameBoard.innerHTML = '';
    for (let i = 0; i < 6; i++) {
        const row = document.createElement('div');
        row.className = 'word-row';
        for (let j = 0; j < 5; j++) {
            const tile = document.createElement('div');
            tile.className = 'letter-tile';
            tile.id = `tile-${i}-${j}`;
            row.appendChild(tile);
        }
        gameBoard.appendChild(row);
    }
}

// Update game statistics
function updateStats() {
    attemptCount.textContent = game.attempts.length;
    remainingAttempts.textContent = game.remaining_attempts;
}

// Show message
function showMessage(text, type = 'info') {
    message.textContent = text;
    message.className = `message ${type}`;
    message.classList.remove('hidden');
}

// Hide message
function hideMessage() {
    message.classList.add('hidden');
}

// Update keyboard colors based on letter states
function updateKeyboard(result) {
    result.forEach(letterState => {
        const key = document.querySelector(`[data-key="${letterState.character.toLowerCase()}"]`);
        if (key) {
            if (letterState.is_in_position) {
                key.classList.add('correct');
            } else if (letterState.is_in_word) {
                key.classList.add('present');
            } else {
                key.classList.add('absent');
            }
        }
    });
}

// Animate tiles
function animateTiles(row, result) {
    result.forEach((letterState, index) => {
        const tile = document.getElementById(`tile-${row}-${index}`);
        setTimeout(() => {
            if (letterState.is_in_position) {
                tile.classList.add('correct');
            } else if (letterState.is_in_word) {
                tile.classList.add('present');
            } else {
                tile.classList.add('absent');
            }
        }, index * 100);
    });
}

// Submit guess
function submitGuess() {
    console.log("submitGuess called", currentGuess);

    const guess = currentGuess.toUpperCase().trim();

    if (!allowedWords.includes(currentGuess)) {
        showMessage("Not a valid word", "error");
        return;
    }

    if (guess.length !== 5) {
        showMessage('Word must be 5 letters!', 'error');
        return;
    }

    if (!game.can_attempt) {
        showMessage('Game is over!', 'error');
        return;
    }

    game.attempt(guess);
    const result = game.guess(guess);

    // Fill current row with guess and animate result
    result.forEach((letterState, index) => {
        const tile = document.getElementById(`tile-${currentRow}-${index}`);
        tile.textContent = letterState.character;
        tile.classList.add('filled');
    });

    animateTiles(currentRow, result);
    updateKeyboard(result);
    updateStats();

    console.log("Evaluating endgame conditions");
    console.log("is_solved:", game.is_solved);
    console.log("can_attempt:", game.can_attempt);
    console.log("attempts:", game.attempts);
    console.log("secret:", game.secret);

    if (game.is_solved) {
        console.log("Game is solved; entering if statement")

        finalScore = game.attempts.length; // Store the final score
        showMessage(`Congratulations! You solved it in ${game.attempts.length} attempts!`, 'success');
        gameOver = true;
        
        // Send score to parent bot (if running in Telegram)
        console.log("Sending game data back to bot");
        tg.sendData(JSON.stringify({
            action: 'game_completed',
            score: finalScore,
            attempts: game.attempts.length,
            secret_word: game.secret
        }));
    } else if (!game.can_attempt) {

        console.log("Game is failed; entering else block")

        finalScore = 0; // No score if failed
        showMessage(`Game Over! The word was: ${game.secret}`, 'error');
        gameOver = true;
        
        // Send failure to parent bot (if running in Telegram)
        console.log("Sending game data back to bot");
        tg.sendData(JSON.stringify({
            action: 'game_completed',
            score: finalScore,
            attempts: game.attempts.length,
            secret_word: game.secret,
            failed : true
        }));
    }
    // Move to next row
    currentRow++;
    currentGuess = '';
    
}
// Handle keyboard input
function handleKeyPress(key) {
    if (gameOver) return;

    if (key === 'enter' && currentGuess.length === 5) {
        submitGuess();
    } else if (key === 'backspace') {
        if (currentGuess.length > 0) {
            currentGuess = currentGuess.slice(0, -1);
            const tile = document.getElementById(`tile-${currentRow}-${currentGuess.length}`);
            tile.textContent = '';
            tile.classList.remove('filled');
        }
    } else if (key.length === 1 && /[a-zA-Z]/.test(key)) {
        if (currentGuess.length < 5) {
            const index = currentGuess.length;
            currentGuess += key.toUpperCase();
            const tile = document.getElementById(`tile-${currentRow}-${index}`);
            tile.textContent = key.toUpperCase();
            tile.classList.add('filled');
        }
    }
}

// Virtual keyboard
keyboard.addEventListener('click', (e) => {
    if (e.target.classList.contains('key')) {
        const key = e.target.dataset.key;
        handleKeyPress(key);
    }
});

// Physical keyboard
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        submitGuess();
    } else if (e.key === 'backspace') {
        handleKeyPress(e.key)
        return;
    } else if (e.key.length === 1 && /[a-zA-Z]/.test(e.key)) {
        handleKeyPress(e.key)
    }
});

// Initialize game when page loads
document.addEventListener('DOMContentLoaded', () => {
    Promise.all([
        fetch("allowed_words.txt").then(res => res.text()),
        fetch("possible_words.txt").then(res => res.text())
    ]).then(([allowedText, possibleText]) => {
        console.log("Reading in allowed word list")
        allowedWords = allowedText
            .split('\n')
            .map(w => w.trim().toUpperCase())
            .filter(w => w.length === 5);

        console.log("Reading in possible word list")
        const possibleWords = possibleText
            .split('\n')
            .map(w => w.trim().toUpperCase())
            .filter(w => w.length === 5);

        console.log("Shuffling possible words")
        const shuffled = getShuffledWordList(possibleWords);
        const index = getTodayIndex();
        secretWord = shuffled[index % shuffled.length];

        console.log("Today's word:", secretWord);  // comment this out in production
        initGame(secretWord);
    }).catch(err => {
        console.error("Error loading word lists:", err);
    });
})