import copy
import sys

class Switch():
	def __init__(self, nPort, nIdle):
		self.nPort = nPort
		self.nIdle = nIdle
		self.nUnavailable = nPort - nIdle
		self.isUsed = False

	def renew(self):
		self.nIdle = self.nPort - self.nUnavailable
		self.isUsed = False

	def plugin(self, n):
		if self.nIdle < n:
			return -1
		self.nIdle -= n
		self.isUsed = True
		return 0

	def isFull(self):
		if self.nIdle == 0:
			return True
		if self.nIdle < 0:
			print('*** Port Error ***')
			return True

class SwitchPool:
	def __init__(self, label, start_sw, real_sw):
		self.label = label
		self.nFullyUsed = 0
		self.poolSw = real_sw
		self.currentSw = start_sw

	def plugin(self, n, hard=True):
		## hard: IFが不足の場合、余剰IFがあっても使用しない。（Leaf用）
		if self.currentSw.plugin(n) == -1:
			self.nFullyUsed += 1
			n_delta = n - self.currentSw.nIdle
			self.currentSw = copy.copy(self.poolSw)
			if hard == False:
				self.currentSw.plugin(n_delta)
			else:
				self.currentSw.plugin(n)
			print('😨新しい＜%s＞が追加された。現在、＜%s＞%d台は既に利用済み。' % (self.label, self.label, self.nFullyUsed))
			return -1
		return 0

	def showInfo(self):
		print('There are %d fully used %s switchs.' % (self.nFullyUsed, self.label))
		print('Current switch has %d IFs idle.' % (self.currentSw.nIdle))

	def getPoolInfo(self):
		return {'label': self.label, 'used': self.nFullyUsed}

	def getCurrentInfo(self):
		nPortAvailable = self.currentSw.nPort - self.currentSw.nUnavailable
		nPortUsed = nPortAvailable - self.currentSw.nIdle
		return (nPortUsed, nPortAvailable)


class Tsukuba:
	def __init__(self):
		self.leafPool = SwitchPool('Leaf', Switch(96, 37), Switch(96, 88))
		self.mgmtPool = SwitchPool('Mgmt', Switch(48, 6), Switch(48, 46))

	def newServerPlugin(self):
		if self.leafPool.plugin(4) == -1:
			self.__event_newLeafPlugin()
		if self.mgmtPool.plugin(1, False) == -1:
			self.__event_newMgmtPlugin()

	def __event_newLeafPlugin(self):
		## 1 leaf group uses 4 mgmt ports:
		## ZTP * 2
		## Mgmt * 2
		print('*** 追加Leafが、MgmtにZTP*2+Mgmt*2を占用する。')
		if self.mgmtPool.plugin(4, False) == -1:
			print('*** Leaf追加によりMgmt枯渇が発生。')
			self.__event_newMgmtPlugin()

	def __event_newMgmtPlugin(self):
		## 1 mgmt uses 2 leaf group ports
		## Communication * 2
		print('*** 追加Mgmtが、Leafに経路*2を占用する。')
		if self.leafPool.plugin(2) == -1:
			print('*** Mgmt追加によりLeaf枯渇が発生。')
			self.__event_newLeafPlugin()

	def showPools(self):
		self.leafPool.showInfo()
		self.mgmtPool.showInfo()

	def showPoolInfo(self):
		dic_leaf = self.leafPool.getPoolInfo()
		dic_mgmt = self.mgmtPool.getPoolInfo()
		print('＜%s＞%d台が追加必要。' % (dic_leaf['label'], dic_leaf['used']))
		print('＜%s＞%d台が追加必要。' % (dic_mgmt['label'], dic_mgmt['used']))


def main():
	N_SRV = int(sys.argv[1])
	datacenter = Tsukuba()
	for i in range(N_SRV):
		datacenter.newServerPlugin()
		info_leaf = datacenter.leafPool.getCurrentInfo()
		info_mgmt = datacenter.mgmtPool.getCurrentInfo()
		print('第 %d 台SV追加済み。IF利用状況：Leaf(%d/%d), Mgmt(%d/%d)' % \
			(i+1, info_leaf[0], info_leaf[1], info_mgmt[0], info_mgmt[1]))
	print('----------------')
	dic_result = datacenter.showPoolInfo()


if __name__ == '__main__':
	main()