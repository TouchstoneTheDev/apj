// Starting fresh to build the top-down kitchen game.
const config = {
    type: Phaser.AUTO,
    width: 800,
    height: 600,
    scene: {
        preload: preload,
        create: create,
        update: update
    },
    physics: {
        default: 'arcade',
        arcade: {
            gravity: { y: 0 }, // No gravity for top-down view
            debug: false
        }
    }
};

const game = new Phaser.Game(config);

// Game variables
let player;
let cursors;
let dirtyDishPileZone, sinkZone, dryingRackZone;
let carriedDish = null;
let instructionText, scoreText;
let score = 0;
const DISHES_TO_WIN = 5;
let gameOver = false;

function preload() {
    this.load.spritesheet('porter', 'assets/porter.png', { frameWidth: 32, frameHeight: 48 });
    this.load.image('dish', 'assets/dish.png');
}

function create() {
    this.cameras.main.setBackgroundColor('#EFEFEF'); // Light grey background

    // --- Interaction Zones & Visuals ---
    dirtyDishPileZone = this.add.zone(100, 300, 150, 200);
    this.physics.world.enable(dirtyDishPileZone);
    this.add.rectangle(100, 300, 150, 200, 0x8B4513, 0.3);
    this.add.text(100, 300, 'Dirty\nDishes', { align: 'center', fill: '#fff' }).setOrigin(0.5);

    sinkZone = this.add.zone(400, 300, 150, 150);
    this.physics.world.enable(sinkZone);
    this.add.rectangle(400, 300, 150, 150, 0xC0C0C0, 0.5);
    this.add.text(400, 300, 'Sink', { align: 'center' }).setOrigin(0.5);

    dryingRackZone = this.add.zone(700, 300, 150, 200);
    this.physics.world.enable(dryingRackZone);
    this.add.rectangle(700, 300, 150, 200, 0xA9A9A9, 0.5);
    this.add.text(700, 300, 'Drying\nRack', { align: 'center' }).setOrigin(0.5);

    // --- Player Setup ---
    player = this.physics.add.sprite(400, 500, 'porter', 4); // Start with forward-facing frame
    player.setCollideWorldBounds(true);

    // --- UI ---
    instructionText = this.add.text(400, 50, 'Go to the dirty dishes and press SPACE.', { fontSize: '18px', fill: '#000' }).setOrigin(0.5);
    scoreText = this.add.text(400, 80, `Dishes Washed: 0 / ${DISHES_TO_WIN}`, { fontSize: '18px', fill: '#000' }).setOrigin(0.5);

    // --- Controls ---
    cursors = this.input.keyboard.createCursorKeys();
}

function update() {
    if (gameOver) {
        player.setVelocity(0);
        return;
    }

    // --- Player Movement ---
    player.setVelocity(0);
    if (cursors.left.isDown) player.setVelocityX(-200);
    else if (cursors.right.isDown) player.setVelocityX(200);
    if (cursors.up.isDown) player.setVelocityY(-200);
    else if (cursors.down.isDown) player.setVelocityY(200);

    // --- Interaction Logic ---
    const spacePressed = Phaser.Input.Keyboard.JustDown(cursors.space);
    const isOverDirtyPile = this.physics.overlap(player, dirtyDishPileZone);
    const isOverSink = this.physics.overlap(player, sinkZone);
    const isOverDryingRack = this.physics.overlap(player, dryingRackZone);

    if (spacePressed) {
        if (isOverDirtyPile && !carriedDish) {
            carriedDish = this.add.sprite(player.x, player.y - 40, 'dish').setTint(0x8B4513);
            carriedDish.isDirty = true;
            instructionText.setText('Take the dish to the sink.');
        } else if (isOverSink && carriedDish && carriedDish.isDirty) {
            instructionText.setText('Washing...');
            this.time.delayedCall(1500, () => {
                carriedDish.clearTint();
                carriedDish.isDirty = false;
                instructionText.setText('Take the clean dish to the drying rack.');
            });
        } else if (isOverDryingRack && carriedDish && !carriedDish.isDirty) {
            carriedDish.destroy();
            carriedDish = null;
            score++;
            scoreText.setText(`Dishes Washed: ${score} / ${DISHES_TO_WIN}`);

            if (score >= DISHES_TO_WIN) {
                gameOver = true;
                instructionText.setText('You Win! Mission Complete!');
            } else {
                instructionText.setText('Good job! Get another dish.');
            }
        }
    }

    // Make the dish follow the player
    if (carriedDish) {
        carriedDish.x = player.x;
        carriedDish.y = player.y - 40;
    }
}