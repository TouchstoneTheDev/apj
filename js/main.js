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
            gravity: { y: 0 }, // Top-down, no gravity
            debug: false
        }
    }
};

const game = new Phaser.Game(config);

// Game variables
let player, cursors, carriedDish = null, scoreText, instructionText, timerText;
let score = 0, timeLeft = 60, gameOver = false;
const DISHES_TO_WIN = 5;
let emitter;
let dirtyDishPile, sink, dryingRack;
let dirtyDishesGroup;

function preload() {
    this.load.spritesheet('porter', 'assets/porter.png', { frameWidth: 32, frameHeight: 48 });
    this.load.image('dish', 'assets/dish.png');
    this.load.bitmapFont('iceicebaby', 'assets/fonts/iceicebaby.png', 'assets/fonts/iceicebaby.xml');
    this.load.image('kitchen', 'assets/kitchen.jpg');
}

function create() {
    // --- Kitchen Environment ---
    this.add.image(400, 300, 'kitchen').setDisplaySize(800, 600);

    // --- Placeholder & Effect Textures ---
    const graphics = this.add.graphics();
    graphics.fillStyle(0xFFC0CB, 1); graphics.fillEllipse(30, 20, 60, 40); graphics.generateTexture('wig', 60, 40);
    graphics.fillStyle(0xFFFF00, 1); graphics.fillTriangle(0, 50, 25, 0, 50, 50); graphics.generateTexture('topa', 50, 50);
    graphics.fillStyle(0xffffff, 1); graphics.fillCircle(5, 5, 5); graphics.generateTexture('sparkle', 10, 10);
    graphics.destroy();

    // --- Interaction Zones & Visuals ---
    // Dirty Dish Pile
    dirtyDishPile = this.add.zone(120, 350, 150, 150);
    this.physics.world.enable(dirtyDishPile);
    dirtyDishPile.body.setAllowGravity(false);
    this.add.text(120, 420, 'Dirty Dishes', { fontSize: '20px', fill: '#000', backgroundColor: '#fff' }).setOrigin(0.5);

    // Sink (position over the sink in the background image)
    sink = this.add.zone(400, 350, 200, 150);
    this.physics.world.enable(sink);
    sink.body.setAllowGravity(false);
    this.add.text(400, 420, 'Sink', { fontSize: '20px', fill: '#000', backgroundColor: '#fff' }).setOrigin(0.5);

    // Drying Rack
    dryingRack = this.add.zone(680, 350, 150, 150);
    this.physics.world.enable(dryingRack);
    dryingRack.body.setAllowGravity(false);
    this.add.rectangle(680, 350, 150, 120, 0xBDC3C7, 0.8).setStrokeStyle(3, 0x7F8C8D);
    this.add.text(680, 350, 'Drying Rack').setOrigin(0.5);

    // --- Visual Dish Stacks ---
    dirtyDishesGroup = this.add.group();
    for (let i = 0; i < DISHES_TO_WIN; i++) {
        dirtyDishesGroup.create(120, 350 - (i * 5), 'dish').setTint(0x654321);
    }

    // --- Player ---
    player = this.physics.add.sprite(400, 500, 'porter');
    player.setCollideWorldBounds(true);

    this.anims.create({ key: 'left', frames: this.anims.generateFrameNumbers('porter', { start: 0, end: 3 }), frameRate: 10, repeat: -1 });
    this.anims.create({ key: 'turn', frames: [ { key: 'porter', frame: 4 } ], frameRate: 20 });
    this.anims.create({ key: 'right', frames: this.anims.generateFrameNumbers('porter', { start: 5, end: 8 }), frameRate: 10, repeat: -1 });

    // --- UI and Effects ---
    emitter = this.add.particles('sparkle').createEmitter({ speed: 100, scale: { start: 1, end: 0 }, blendMode: 'ADD', lifespan: 600, on: false });
    const uiBackground = this.add.rectangle(400, 550, 780, 80, 0x000000, 0.7);
    instructionText = this.add.bitmapText(400, 530, 'iceicebaby', `Wash ${DISHES_TO_WIN} dishes!`, 20, 1).setOrigin(0.5);
    scoreText = this.add.bitmapText(200, 560, 'iceicebaby', `Washed: 0 / ${DISHES_TO_WIN}`, 28, 1).setOrigin(0.5);
    timerText = this.add.bitmapText(600, 560, 'iceicebaby', `Time: 60`, 28, 1).setOrigin(0.5);

    // --- Easter Egg ---
    const wig = this.add.sprite(750, 50, 'wig').setInteractive();
    const topa = this.add.sprite(750, 50, 'topa').setVisible(false);
    wig.on('pointerdown', () => { topa.setVisible(true); wig.setVisible(false); });

    // --- Timer and Controls ---
    this.missionTimer = this.time.addEvent({ delay: 1000, callback: () => {
        if (!gameOver) {
            timeLeft--;
            timerText.setText(`Time: ${timeLeft}`);
            if (timeLeft <= 0) {
                endGame.call(this, false);
            }
        }
    }, loop: true });
    cursors = this.input.keyboard.createCursorKeys();
}

function endGame(isWin) {
    if (gameOver) return; // Prevent endGame from being called multiple times
    gameOver = true;
    this.missionTimer.remove(false); // Stop the timer
    this.physics.pause();
    player.anims.play('turn');
    let message = isWin ? 'You Win!' : 'Time\'s Up!';
    const endText = this.add.bitmapText(400, 300, 'iceicebaby', message + '\nPress R to Restart', 48, 1).setOrigin(0.5).setCenterAlign();

    this.input.keyboard.on('keydown-R', () => {
        score = 0; timeLeft = 60; gameOver = false; carriedDish = null; this.scene.restart();
    });
}

function update() {
    if (gameOver) return;

    // Player Movement
    player.setVelocity(0);
    if (cursors.left.isDown) { player.setVelocityX(-200); player.anims.play('left', true); }
    else if (cursors.right.isDown) { player.setVelocityX(200); player.anims.play('right', true); }
    else if (cursors.up.isDown) { player.setVelocityY(-200); player.anims.play('turn', true); }
    else if (cursors.down.isDown) { player.setVelocityY(200); player.anims.play('turn', true); }
    else { player.anims.play('turn'); }

    // Interaction Text
    const isOverDirtyPile = this.physics.overlap(player, dirtyDishPile);
    const isOverSink = this.physics.overlap(player, sink);
    const isOverDryingRack = this.physics.overlap(player, dryingRack);
    instructionText.setVisible(false);

    if (!carriedDish) {
        if (isOverDirtyPile && dirtyDishesGroup.countActive(true) > 0) {
            instructionText.setText('Press SPACE to pick up a dish.');
            instructionText.setVisible(true);
        }
    } else {
        if (carriedDish.isDirty) {
            if (isOverSink) { instructionText.setText('Press SPACE to wash.'); instructionText.setVisible(true); }
            else { instructionText.setText('Take the dish to the sink.'); instructionText.setVisible(true); }
        } else {
            if (isOverDryingRack) { instructionText.setText('Press SPACE to place the dish.'); instructionText.setVisible(true); }
            else { instructionText.setText('Take the clean dish to the drying rack.'); instructionText.setVisible(true); }
        }
    }

    // Action Handling
    const spacePressed = Phaser.Input.Keyboard.JustDown(cursors.space);
    if (spacePressed) {
        if (isOverDirtyPile && !carriedDish && dirtyDishesGroup.countActive(true) > 0) {
            let dishToTake = dirtyDishesGroup.getLast(true);
            if (dishToTake) {
                dishToTake.destroy();
                carriedDish = this.add.sprite(player.x, player.y - 40, 'dish').setTint(0x654321);
                carriedDish.isDirty = true;
            }
        } else if (isOverSink && carriedDish && carriedDish.isDirty) {
            this.time.delayedCall(1000, () => {
                carriedDish.clearTint();
                carriedDish.isDirty = false;
                emitter.explode(20, carriedDish.x, carriedDish.y);
            });
        } else if (isOverDryingRack && carriedDish && !carriedDish.isDirty) {
            carriedDish.destroy();
            carriedDish = null;
            this.add.sprite(680, 350 - (score * 5), 'dish');
            score++;
            scoreText.setText(`Washed: ${score} / ${DISHES_TO_WIN}`);
            if (score >= DISHES_TO_WIN) endGame.call(this, true);
        }
    }

    // Carried Dish Follow
    if (carriedDish) { carriedDish.x = player.x; carriedDish.y = player.y - 40; }
}