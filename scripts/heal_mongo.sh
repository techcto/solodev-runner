#!/bin/bash
	
REPLICAS=()
ARBITERS=()
BADHOSTS=()

in_array() {
	local haystack=${1}[@]
	local needle=${2}
	for i in ${!haystack}; do
		if [[ ${i} == ${needle} ]]; then
			return 0
		fi
	done
	return 1
}

SETNAME=$(echo 'rs.status()'| mongo | egrep "set" | awk -F \" '{print $4}'| cut -f 1 -d :)

#Add buffer to wait for servers to go out of service.
sleep 60

#Loop through status and get ids
IDS=()
for id in `echo 'rs.status()' | mongo | egrep "_id" | awk -F : '{print $2}'| cut -f 1 -d ,`; do 
	echo $id
	IDS=(${IDS[@]} "$id")
done 

## Check whether host is slave and in good state 
HOSTCOUNT=0
for i in `echo "rs.status()" | mongo | egrep "name" | awk -F \" '{print $4}'| cut -f 1 -d :`; do 
	echo $i
	TheState=$(echo "rs.status()"| mongo --host $i | grep -i mystate | awk -F ":" '{print $2}' | cut -f 1 -d ,) 
	
	CURRENT_ID=${IDS[$HOSTCOUNT]}
	
	if [ $TheState ]; then 
		echo '$i is accessible.'
		
		#Add into available replicas array
		host=$(echo $i | sed -r 's/ip-//g' | sed -r 's/-/\./g')
		
		#Test if master
		IsMaster=$(echo "db.isMaster()"| mongo --host $i | grep ismaster| awk -F ":" '{print $2}' | cut -f 1 -d ,)
		if [ $IsMaster == "true" ]; then 
			echo '$i is Master.'
			REPLICAS[$CURRENT_ID]=$host
			MASTER=$host
		elif [ $TheState == "7" ]; then 
			ARBITERS[$CURRENT_ID]=$host
		else
			echo '$i is Slave.'
			REPLICAS[$CURRENT_ID]=$host
			REPLICA=$host
		fi
	else
		echo '$i not accessible.  Remove from Replica'
		
		#Add into remove replicas array
		BADHOSTS=(${BADHOSTS[@]} $i)
	fi 
	
	HOSTCOUNT=$((HOSTCOUNT+1))
done 

if [ $MASTER ]; then
	MONGOHOST=$MASTER
else
	MONGOHOST=$REPLICA
fi

#echo "${REPLICAS[@]}"
#Check available hosts to see if we have new available replicas to add
HOSTID=$((CURRENT_ID+1))
set -- junk $AWSHOSTS
shift
for host; do
	if in_array REPLICAS "$host"; then 
		echo '$host is already a replica'
	else 
		echo '$host is not a replica. Add host into available replicas'
		REPLICAS[$HOSTID]=$host
		HOSTID=$((HOSTID+1))
		ADDHOSTS=1
	fi
done

mongoconfig='config = {"_id" : "'$SETNAME'", "members" : ['
REPLICACOUNT=0
CANVOTE=1
#Loop through available replicas and reconfigure mongo replica group

for id in "${!REPLICAS[@]}"; do
	if [ $REPLICACOUNT -gt "0" ]; then
		mongoconfig+=", "
	fi
	if [ $REPLICACOUNT -gt "6" ]; then
		CANVOTE=0
	fi
	mongoconfig+='{"_id" : '$id', "host" : "'${REPLICAS[$id]}':27017", "votes" : '$CANVOTE'}'
	REPLICACOUNT=$((REPLICACOUNT+1))
done

for id in "${!ARBITERS[@]}"; do
	if [ $REPLICACOUNT -gt "0" ]; then
		mongoconfig+=", "
	fi
	mongoconfig+='{"_id" : '$id', "host" : "'${ARBITERS[$id]}':27017", "arbiterOnly" : true}'
	REPLICACOUNT=$((REPLICACOUNT+1))
done

mongoconfig+=']};'
mongoconfig+='rs.reconfig(config, {force : true});'

echo "$mongoconfig"

if [ $BADHOSTS ] || [ $ADDHOSTS ]; then 
	echo "$mongoconfig" | mongo --host $MONGOHOST
fi

#service mongod stop
#service mongod start