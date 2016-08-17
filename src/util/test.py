import gym
import numpy as np
def test():
    env = gym.make('CollaborativeFiltering-v0')
    # env = gym.make('CartPole-v0')
    # env.monitor.start('/tmp/cartpole-experiment-1')
    # env.reset()
    # for _ in range(1000):
    #     env.render()
    #     env.step(env.action_space.sample()) # take a random action

    R = []
    for i_episode in range(2000):
        rew = 0.
        observation = env.reset()
        for t in range(100):
            env.render()
            # print(observation)
            action = env.action_space.sample()
            observation, reward, done, info = env.step(action)
            rew += reward

            # print(info)
            if done:
                R.append(rew / (t + 1))
                print("Episode finished after {} timesteps. Average Reward {}".format(t+1, np.mean(R)))
                break
        print "Episode {} Average Reward per user: {}".format(i_episode, rew)
        avr = np.mean(R)
        if env.spec.reward_threshold is not None and avr > env.spec.reward_threshold:
            print "Threshold reached {} > {}".format(avr, env.spec.reward_threshold)
            break

    env.monitor.close()

if __name__ == "__main__":
    test()