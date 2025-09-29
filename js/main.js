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
            gravity: { y: 400 },
            debug: false // Ensure debug is off
        }
    }
};

const game = new Phaser.Game(config);

// Game variables
let player, cursors, dirtyDishPile, sink, dryingRack, carriedDish = null, scoreText, timerText, instructionText;
let score = 0, timeLeft = 60, gameOver = false;
const DISHES_TO_WIN = 5;
let emitter;

// Sound placeholders
const sounds = {
    pickup: null,
    wash: null,
    score: null,
    jump: null,
    win: null,
    lose: null
};

function preload() {
    this.load.spritesheet('porter', 'assets/porter.png', { frameWidth: 32, frameHeight: 48 });
    this.load.image('dish', 'assets/dish.png');
}

function create() {
    // --- Kitchen Environment ---
    this.cameras.main.setBackgroundColor('#D3D3D3');

    const platforms = this.physics.add.staticGroup();
    platforms.create(400, 580, 'ground').setScale(2).refreshBody();
    platforms.create(150, 450, 'platform'); // Dish pile platform
    platforms.create(400, 350, 'platform'); // Sink platform
    platforms.create(650, 450, 'platform'); // Drying rack platform

    // --- Placeholder Textures ---
    const graphics = this.add.graphics();
    graphics.fillStyle(0x663300, 1);
    graphics.fillRect(0, 0, 400, 32);
    graphics.generateTexture('ground', 400, 32);
    graphics.fillStyle(0xA0522D, 1);
    graphics.fillRect(0, 0, 200, 32);
    graphics.generateTexture('platform', 200, 32);
    graphics.fillStyle(0xFFC0CB, 1);
    graphics.fillEllipse(30, 20, 60, 40);
    graphics.generateTexture('wig', 60, 40);
    graphics.fillStyle(0xFFFF00, 1);
    graphics.fillTriangle(0, 50, 25, 0, 50, 50);
    graphics.generateTexture('topa', 50, 50);
    graphics.fillStyle(0xffffff, 1);
    graphics.fillCircle(5, 5, 5);
    graphics.generateTexture('sparkle', 10, 10);
    graphics.destroy();

    // --- Interaction Zones & Visuals ---
    dirtyDishPile = this.add.zone(150, 420, 100, 50);
    this.physics.world.enable(dirtyDishPile);
    dirtyDishPile.body.setAllowGravity(false);
    this.add.sprite(150, 420, 'dish').setTint(0x654321).setScale(2).setAlpha(0.7);
    this.add.text(150, 420, 'Dirty\nDishes', { align: 'center', fill: '#fff' }).setOrigin(0.5);

    sink = this.add.zone(400, 320, 100, 50);
    this.physics.world.enable(sink);
    sink.body.setAllowGravity(false);
    this.add.rectangle(400, 320, 100, 50, 0xAAAAFF, 0.7);
    this.add.text(400, 320, 'Sink', { align: 'center' }).setOrigin(0.5);

    dryingRack = this.add.zone(650, 420, 100, 50);
    this.physics.world.enable(dryingRack);
    dryingRack.body.setAllowGravity(false);
    this.add.rectangle(650, 420, 100, 50, 0x999999, 0.7);
    this.add.text(650, 420, 'Drying\nRack', { align: 'center' }).setOrigin(0.5);

    // --- Player ---
    player = this.physics.add.sprite(50, 500, 'porter');
    player.setBounce(0.1);
    player.setCollideWorldBounds(true);
    this.physics.add.collider(player, platforms);

    this.anims.create({ key: 'left', frames: this.anims.generateFrameNumbers('porter', { start: 0, end: 3 }), frameRate: 10, repeat: -1 });
    this.anims.create({ key: 'turn', frames: [ { key: 'porter', frame: 4 } ], frameRate: 20 });
    this.anims.create({ key: 'right', frames: this.anims.generateFrameNumbers('porter', { start: 5, end: 8 }), frameRate: 10, repeat: -1 });

    // --- Particle Emitter ---
    emitter = this.add.particles('sparkle').createEmitter({
        speed: 100,
        scale: { start: 1, end: 0 },
        blendMode: 'ADD',
        lifespan: 600,
        on: false
    });

    // --- Easter Egg ---
    const wig = this.add.sprite(20, 20, 'wig').setInteractive();
    const topa = this.add.sprite(20, 20, 'topa').setVisible(false);
    wig.on('pointerdown', () => {
        topa.setVisible(true);
        wig.setVisible(false);
    });

    // --- UI ---
    const uiBackground = this.add.rectangle(400, 50, 760, 80, 0x000000, 0.5);
    instructionText = this.add.text(400, 30, `Wash ${DISHES_TO_WIN} dishes!`, { fontSize: '18px', fill: '#fff' }).setOrigin(0.5);
    scoreText = this.add.text(200, 60, `Washed: 0 / ${DISHES_TO_WIN}`, { fontSize: '24px', fill: '#fff' }).setOrigin(0.5);
    timerText = this.add.text(600, 60, `Time: ${timeLeft}`, { fontSize: '24px', fill: '#fff' }).setOrigin(0.5);

    // --- Timer ---
    this.time.addEvent({
        delay: 1000,
        callback: () => {
            if (!gameOver) {
                timeLeft--;
                timerText.setText(`Time: ${timeLeft}`);
                if (timeLeft <= 0) {
                    endGame.call(this, false);
                }
            }
        },
        loop: true
    });

    cursors = this.input.keyboard.createCursorKeys();
}

function endGame(isWin) {
    gameOver = true;
    this.physics.pause();
    player.anims.play('turn');
    let message = isWin ? 'You Win!' : 'Time\'s Up!';
    if (isWin) { /* sounds.win.play(); */ } else { /* sounds.lose.play(); */ }
    const endText = this.add.text(400, 300, message + '\nPress R to Restart', { fontSize: '48px', fill: '#ff0000', backgroundColor: '#000', align: 'center' }).setOrigin(0.5);

    this.input.keyboard.on('keydown-R', () => {
        // Reset state
        score = 0;
        timeLeft = 60;
        gameOver = false;
        carriedDish = null;
        this.scene.restart();
    });
}

function update() {
    if (gameOver) return;

    // --- Player Movement ---
    if (cursors.left.isDown) {
        player.setVelocityX(-160);
        player.anims.play('left', true);
    } else if (cursors.right.isDown) {
        player.setVelocityX(160);
        player.anims.play('right', true);
    } else {
        player.setVelocityX(0);
        player.anims.play('turn');
    }
    if (cursors.up.isDown && player.body.touching.down) {
        player.setVelocityY(-330);
        /* sounds.jump.play(); */
    }

    // --- Interaction Text Handling ---
    const isOverDirtyPile = this.physics.overlap(player, dirtyDishPile);
    const isOverSink = this.physics.overlap(player, sink);
    const isOverDryingRack = this.physics.overlap(player, dryingRack);
    let instructionVisible = false;

    if (!carriedDish) {
        if (isOverDirtyPile) {
            instructionText.setText('Press SPACE to pick up a dish.');
            instructionVisible = true;
        }
    } else {
        if (carriedDish.isDirty) {
            if (isOverSink) {
                instructionText.setText('Press SPACE to wash the dish.');
                instructionVisible = true;
            } else {
                instructionText.setText('Take the dish to the sink.');
                instructionVisible = true;
            }
        } else {
            if (isOverDryingRack) {
                instructionText.setText('Press SPACE to place the dish.');
                instructionVisible = true;
            } else {
                instructionText.setText('Take the clean dish to the drying rack.');
                instructionVisible = true;
            }
        }
    }
    instructionText.setVisible(instructionVisible);


    // --- Action Handling ---
    const spacePressed = Phaser.Input.Keyboard.JustDown(cursors.space);
    if (spacePressed) {
        if (isOverDirtyPile && !carriedDish) {
            carriedDish = this.add.sprite(player.x, player.y - 40, 'dish').setTint(0x654321);
            carriedDish.isDirty = true;
            // sounds.pickup.play();
        } else if (isOverSink && carriedDish && carriedDish.isDirty) {
            this.time.delayedCall(1000, () => {
                carriedDish.clearTint();
                carriedDish.isDirty = false;
                emitter.explode(20, carriedDish.x, carriedDish.y);
                // sounds.wash.play();
            });
        } else if (isOverDryingRack && carriedDish && !carriedDish.isDirty) {
            carriedDish.destroy();
            carriedDish = null;
            score++;
            scoreText.setText(`Washed: ${score} / ${DISHES_TO_WIN}`);
            // sounds.score.play();
            if (score >= DISHES_TO_WIN) {
                endGame.call(this, true);
            }
        }
    }

    // --- Carried Dish Follow ---
    if (carriedDish) {
        carriedDish.x = player.x;
        carriedDish.y = player.y - 40;
    }
}